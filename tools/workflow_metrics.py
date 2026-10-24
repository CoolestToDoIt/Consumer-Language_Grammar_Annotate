"""User-workflow metrics for the gloss teaching loop.

Part 1 replays the core product workflow on a development language: a user
imports unglossed sentences in corpus order, sees the model's suggestion for
each word, accepts it, picks another listed candidate, or types the answer,
then submits the verified sentence as a correction. Every suggestion is made
before that sentence's answer is taught. Part 2 freezes the fully taught model
and measures whether the review ordering surfaces mistakes early on unseen
development sentences. Scores are empirical rates, not calibrated confidence.
"""
import argparse
import json
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from decipher.gloss import GlossLearner, lexical_key  # noqa: E402
from decipher.gloss_backoff import BackoffGlossLearner  # noqa: E402
from decipher.gloss_evaluate import prepare  # noqa: E402
from decipher.review import relative_margin  # noqa: E402

WINDOW = 50
MILESTONES = (0.5, 0.6, 0.7)
BUDGETS = (0.1, 0.2, 0.3, 0.5)


def ratio(a, b):
    return a/b if b else None


def percentile(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered)-1, int(q*len(ordered)))] if ordered else None


def teaching_session(training, learner):
    totals = dict.fromkeys(('words', 'accepted', 'picked', 'typed', 'abstained', 'wrong_guess',
                            'gloss_chars', 'typed_chars', 'zero_edit_sentences',
                            'repeat_words', 'repeat_correct', 'repeat_same_answer', 'repeat_same_answer_correct',
                            'new_form_words', 'new_form_correct', 'new_form_grammatical', 'new_form_grammatical_correct'), 0)
    taught_pairs, curve, rolling, predict_ms, correct_ms = set(), [], [], [], []
    milestones = {f'{int(m*100)}%': None for m in MILESTONES}
    window = dict.fromkeys(('words', 'accepted', 'typed'), 0)
    for index, gold in enumerate(training, 1):
        start = time.perf_counter()
        predictions = learner.predict(gold.example)
        predict_ms.append(1000*(time.perf_counter()-start))
        edits, accepted_here = 0, 0
        for word, target, prediction in zip(gold.example.tokens, gold.glosses, predictions):
            candidates = [row['gloss'] for row in prediction['candidates'][:5]]
            accepted = prediction['gloss'] == target
            picked = not accepted and target in candidates
            known = prediction['known_form']
            totals['words'] += 1
            totals['accepted'] += accepted
            totals['picked'] += picked
            totals['typed'] += not accepted and not picked
            totals['abstained'] += prediction['gloss'] is None
            totals['wrong_guess'] += prediction['gloss'] is not None and not accepted
            totals['gloss_chars'] += len(target)
            totals['typed_chars'] += 0 if accepted or picked else len(target)
            if known:
                totals['repeat_words'] += 1
                totals['repeat_correct'] += accepted
                if (word, target) in taught_pairs:
                    totals['repeat_same_answer'] += 1
                    totals['repeat_same_answer_correct'] += accepted
            else:
                totals['new_form_words'] += 1
                totals['new_form_correct'] += accepted
                if not lexical_key(target):
                    totals['new_form_grammatical'] += 1
                    totals['new_form_grammatical_correct'] += accepted
            edits += not accepted
            accepted_here += accepted
            window['words'] += 1
            window['accepted'] += accepted
            window['typed'] += not accepted and not picked
        totals['zero_edit_sentences'] += edits == 0
        rolling.append((len(predictions), accepted_here))
        rolling = rolling[-WINDOW:]
        rate = sum(a for _, a in rolling)/sum(n for n, _ in rolling)
        for label, threshold in zip(milestones, MILESTONES):
            if milestones[label] is None and len(rolling) == WINDOW and rate >= threshold:
                milestones[label] = index
        start = time.perf_counter()
        learner.correct(gold.example, gold.glosses)
        correct_ms.append(1000*(time.perf_counter()-start))
        taught_pairs.update(zip(gold.example.tokens, gold.glosses))
        if index % WINDOW == 0 or index == len(training):
            curve.append({'sentences_taught_before_window_end': index, 'words': window['words'],
                          'suggestion_acceptance': ratio(window['accepted'], window['words']),
                          'typed_from_scratch': ratio(window['typed'], window['words'])})
            window = dict.fromkeys(window, 0)
    t = totals
    return {
        'sentences': len(training), 'words': t['words'],
        'suggestion_acceptance': ratio(t['accepted'], t['words']),
        'one_click_fix': ratio(t['picked'], t['words']),
        'typed_from_scratch': ratio(t['typed'], t['words']),
        'typing_saved_chars': 1-ratio(t['typed_chars'], t['gloss_chars']),
        'zero_edit_sentences': ratio(t['zero_edit_sentences'], len(training)),
        'abstained_words': ratio(t['abstained'], t['words']),
        'wrong_guess_words': ratio(t['wrong_guess'], t['words']),
        'precision_when_suggesting': ratio(t['accepted'], t['words']-t['abstained']),
        'known_form_accuracy': ratio(t['repeat_correct'], t['repeat_words']),
        'teach_once_reuse': ratio(t['repeat_same_answer_correct'], t['repeat_same_answer']),
        'new_form_accuracy': ratio(t['new_form_correct'], t['new_form_words']),
        'new_form_grammatical_accuracy': ratio(t['new_form_grammatical_correct'], t['new_form_grammatical']),
        'sentences_until_rolling_acceptance': milestones,
        'predict_ms_p50': percentile(predict_ms, .5), 'predict_ms_p95': percentile(predict_ms, .95),
        'correct_ms_p50': percentile(correct_ms, .5), 'correct_ms_p95': percentile(correct_ms, .95),
        'counts': t, 'curve': curve,
    }


def review_triage(learner, probes, seed=0):
    words = []
    for gold in probes:
        for word, target, prediction in zip(gold.example.tokens, gold.glosses, learner.predict(gold.example)):
            # Same signals as the review queue: unsupported, unseen, then low margin.
            priority = (prediction['gloss'] is not None, prediction['known_form'], relative_margin(prediction))
            words.append((priority, prediction['gloss'] != target, prediction))
    errors = sum(wrong for _, wrong, _ in words)
    ranked = [wrong for _, wrong, _ in sorted(words, key=lambda row: row[0])]
    shuffled = [wrong for _, wrong, _ in words]
    random.Random(seed).shuffle(shuffled)
    budgets = {}
    for budget in BUDGETS:
        size = round(budget*len(words))
        budgets[f'{int(budget*100)}%'] = {'review_ordered': ratio(sum(ranked[:size]), errors),
                                          'random_order': ratio(sum(shuffled[:size]), errors)}
    confident = [wrong for (supported, known, margin), wrong, _ in words if supported and known and margin == 1.0]
    flagged = [wrong for (supported, known, margin), wrong, _ in words if not (supported and known and margin == 1.0)]
    return {'words': len(words), 'errors': errors, 'word_accuracy': 1-ratio(errors, len(words)),
            'errors_found_by_review_budget': budgets,
            'auto_accept_share': ratio(len(confident), len(words)),
            'auto_accept_accuracy': 1-ratio(sum(confident), len(confident)) if confident else None,
            'flagged_share': ratio(len(flagged), len(words)),
            'errors_inside_flagged': ratio(sum(flagged), errors)}


def pct(value):
    return 'n/a' if value is None else f'{value:.1%}'


def markdown(report):
    s, r = report['teaching_session'], report['review_triage']
    m = s['sentences_until_rolling_acceptance']
    lines = [f"# Workflow metrics: {report['language']}", '',
             f"Model `{report['config']['mode']}`, guess_unknown={report['config']['guess_unknown']}, "
             f"normalize_unknown={report['config'].get('normalize_unknown', False)}. "
             f"Teaching replay over {s['sentences']} training sentences / {s['words']} words in corpus order, starting from zero annotations; "
             f"review triage on {r['words']} development words with no training-source overlap.", '',
             '## Teaching session (prediction before each correction)', '',
             '| Metric | Value |', '|---|---:|',
             f"| Suggestions accepted as-is | {pct(s['suggestion_acceptance'])} |",
             f"| Fixed by picking a listed candidate | {pct(s['one_click_fix'])} |",
             f"| Typed from scratch | {pct(s['typed_from_scratch'])} |",
             f"| Gloss characters the user did not type | {pct(s['typing_saved_chars'])} |",
             f"| Sentences needing zero edits | {pct(s['zero_edit_sentences'])} |",
             f"| Precision when a suggestion is shown | {pct(s['precision_when_suggesting'])} |",
             f"| Words left blank (\"I don't know\") | {pct(s['abstained_words'])} |",
             f"| Words with a wrong suggestion | {pct(s['wrong_guess_words'])} |",
             f"| Teach-once reuse (same word, same answer as taught) | {pct(s['teach_once_reuse'])} |",
             f"| Accuracy on never-seen word forms | {pct(s['new_form_accuracy'])} |",
             f"| Sentences until rolling-{WINDOW} acceptance ≥50% / 60% / 70% | {m['50%'] or 'not reached'} / {m['60%'] or 'not reached'} / {m['70%'] or 'not reached'} |",
             f"| Predict latency per sentence p50 / p95 | {s['predict_ms_p50']:.2f} / {s['predict_ms_p95']:.2f} ms |",
             f"| Apply-correction latency p50 / p95 | {s['correct_ms_p50']:.2f} / {s['correct_ms_p95']:.2f} ms |",
             '', f'Acceptance by {WINDOW}-sentence window:', '',
             '| Sentences taught | Accepted | Typed from scratch |', '|---:|---:|---:|']
    lines += [f"| {row['sentences_taught_before_window_end']} | {pct(row['suggestion_acceptance'])} | {pct(row['typed_from_scratch'])} |"
              for row in s['curve']]
    lines += ['', '## Review triage (frozen fully-taught model, unseen dev sentences)', '',
              f"Dev word accuracy {pct(r['word_accuracy'])}; {r['errors']} wrong words.", '',
              '| Words reviewed | Errors found (review order) | Errors found (random order) |', '|---:|---:|---:|']
    lines += [f"| {k} | {pct(v['review_ordered'])} | {pct(v['random_order'])} |" for k, v in r['errors_found_by_review_budget'].items()]
    lines += ['', f"Unflagged words (known form, single candidate): {pct(r['auto_accept_share'])} of words at {pct(r['auto_accept_accuracy'])} accuracy. "
              f"Flagged words hold {pct(r['errors_inside_flagged'])} of all errors.", '',
              'Simulated user: an answer counts as accepted only on an exact gloss match. "Picked" means the gold gloss was among the top five listed candidates. '
              'Rates are empirical on this development language and are not calibrated probabilities. Gitksan is not used.']
    return '\n'.join(lines)+'\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--train', required=True)
    parser.add_argument('--dev', required=True)
    parser.add_argument('--language', required=True)
    parser.add_argument('--output', required=True, help='JSON path; Markdown is written alongside')
    parser.add_argument('--mode', default='rules', choices=('memory', 'analogy', 'rules'))
    parser.add_argument('--guess-unknown', action='store_true')
    parser.add_argument('--normalize-unknown', action='store_true', help='opt-in surface-normalization backoff')
    args = parser.parse_args(argv)
    if 'gitksan' in (args.train+args.dev).lower():
        parser.error('Gitksan is reserved for final fresh-language evaluation')
    training, probes, filters = prepare(args.train, args.dev)
    learner = (BackoffGlossLearner if args.normalize_unknown else GlossLearner)(args.mode, guess_unknown=args.guess_unknown)
    report = {'language': args.language, 'config': {'mode': args.mode, 'guess_unknown': args.guess_unknown,
                                                    'normalize_unknown': args.normalize_unknown},
              'filters': {key: value for key, value in filters.items() if key != 'source_overlap_ids_excluded'},
              'teaching_session': teaching_session(training, learner)}
    report['review_triage'] = review_triage(learner, probes)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    destination.with_suffix('.md').write_text(markdown(report), encoding='utf-8')
    print(markdown(report))


if __name__ == '__main__':
    main()
