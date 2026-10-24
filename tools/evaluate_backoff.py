"""Compare the default rule learner with the opt-in normalization backoff on dev data."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from decipher.gloss import GlossLearner  # noqa: E402
from decipher.gloss_backoff import BackoffGlossLearner  # noqa: E402
from decipher.gloss_evaluate import GlossMetrics, prepare  # noqa: E402

KEYS = ('word_accuracy', 'oov_accuracy', 'grounded_oov_accuracy', 'nonpunct_accuracy', 'sentence_accuracy', 'top5_accuracy', 'coverage')


def evaluate(train_path, dev_path):
    training, probes, filters = prepare(train_path, dev_path)
    results = {}
    for name, cls, guess in (('rules', GlossLearner, False), ('rules+backoff', BackoffGlossLearner, False),
                             ('rules+guess', GlossLearner, True), ('rules+backoff+guess', BackoffGlossLearner, True)):
        model = cls('rules', guess_unknown=guess).fit(training)
        metric, shown, shown_right = GlossMetrics(), 0, 0
        for gold in probes:
            predictions = model.predict(gold.example)
            metric.add(gold, predictions, model)
            for target, row in zip(gold.glosses, predictions):
                shown += row['gloss'] is not None
                shown_right += row['gloss'] == target
        result = metric.result()
        results[name] = {**{key: result[key] for key in KEYS}, 'precision_when_suggesting': shown_right/shown if shown else None,
                         'counts': result['counts']}
    return {'training': train_path, 'evaluation': dev_path, 'source_overlaps_excluded': filters['source_overlaps_excluded'],
            'models': results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language', action='append', nargs=3, metavar=('NAME', 'TRAIN', 'DEV'), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    if any('gitksan' in (train+dev).lower() for _, train, dev in args.language):
        parser.error('Gitksan is reserved for final fresh-language evaluation')
    report = {name: evaluate(train, dev) for name, train, dev in args.language}
    lines = ['# Unseen-form normalization backoff (development data)', '',
             '| Language | Model | Word exact | OOV word | Grounded OOV | Sentence exact | Top 5 | Precision when suggesting |',
             '|---|---|---:|---:|---:|---:|---:|---:|']
    for language, block in report.items():
        for name, r in block['models'].items():
            lines.append(f"| {language} | {name} | " + ' | '.join(
                'n/a' if r[k] is None else f'{r[k]:.1%}' for k in
                ('word_accuracy', 'oov_accuracy', 'grounded_oov_accuracy', 'sentence_accuracy', 'top5_accuracy', 'precision_when_suggesting')) + ' |')
    lines += ['', 'Backoff only changes unseen forms: it strips edge punctuation (keeping apostrophe letters) and casefolds, reuses glosses of taught forms with the same key, then retries affix rules. '
              '"guess" is the existing provisional analogy fallback. Development data only; the default engine is unchanged.']
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    destination.with_suffix('.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
