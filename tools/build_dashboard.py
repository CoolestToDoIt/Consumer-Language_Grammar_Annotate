"""Build the self-contained hackathon metrics dashboard from saved report JSON.

Reads reports/hackathon/{workflow,backoff,repro} plus the committed reports used
for the reproduction check, and writes reports/hackathon/dashboard.html with the
data inlined so it opens directly from disk without a server.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HACK = ROOT/'reports'/'hackathon'
LANGUAGES = ('Lezgi', 'Tsez')
SESSION_KEYS = ('suggestion_acceptance', 'one_click_fix', 'typed_from_scratch', 'typing_saved_chars',
                'precision_when_suggesting', 'teach_once_reuse', 'zero_edit_sentences', 'new_form_accuracy',
                'sentences_until_rolling_acceptance', 'predict_ms_p95', 'correct_ms_p95', 'sentences', 'words')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def workflow(language, suffix):
    report = load(HACK/'workflow'/f'{language.lower()}-rules{suffix}.json')
    session, triage = report['teaching_session'], report['review_triage']
    return {**{key: session[key] for key in SESSION_KEYS},
            'curve': [[row['sentences_taught_before_window_end'], row['suggestion_acceptance']] for row in session['curve']],
            'triage': {'budgets': {k: v['review_ordered'] for k, v in triage['errors_found_by_review_budget'].items()},
                       'random': {k: v['random_order'] for k, v in triage['errors_found_by_review_budget'].items()},
                       'word_accuracy': triage['word_accuracy'], 'errors': triage['errors'], 'words': triage['words'],
                       'auto_accept_share': triage['auto_accept_share'], 'auto_accept_accuracy': triage['auto_accept_accuracy']}}


def reproduction():
    rows = []
    for track, committed, fresh, model, key in (
            ('English EWT morphology', 'reports/corpus/english-ewt-test.json', 'repro/english-ewt-test.json', 'affix', 'joint_accuracy'),
            ('Turkish IMST morphology', 'reports/corpus/turkish-imst-test.json', 'repro/turkish-imst-test.json', 'affix', 'joint_accuracy'),
            ('Lezgi glossing', 'reports/gloss/lezgi-dev.json', 'repro/lezgi-dev.json', 'rules', 'word_accuracy'),
            ('Tsez glossing', None, 'repro/tsez-dev.json', 'rules', 'word_accuracy')):
        new = load(HACK/fresh)
        old = load(ROOT/committed)['models'][model][key] if committed else None
        rows.append({'track': track, 'split': new['split'], 'metric': 'joint token' if 'joint' in key else 'word exact',
                     'committed': old, 'reproduced': new['models'][model][key]})
    return rows


def main():
    comparison = load(HACK/'backoff'/'dev-comparison.json')
    data = {'languages': {language: {'default': workflow(language, ''), 'backoff': workflow(language, '-backoff')}
                          for language in LANGUAGES},
            'comparison': {language: {name: {k: comparison[language]['models'][name][k]
                                             for k in ('word_accuracy', 'oov_accuracy', 'precision_when_suggesting')}
                                      for name in ('rules', 'rules+backoff', 'rules+guess')}
                           for language in LANGUAGES},
            'repro': reproduction()}
    html = (Path(__file__).with_name('dashboard_template.html').read_text(encoding='utf-8')
            .replace('__DATA__', json.dumps(data, ensure_ascii=False).replace('</', '<\\/')))
    (HACK/'dashboard.html').write_text(html, encoding='utf-8')
    print(HACK/'dashboard.html')


if __name__ == '__main__':
    main()
