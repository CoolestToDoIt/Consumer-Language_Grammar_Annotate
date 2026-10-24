"""Bounded, source-disjoint development check of B's teaching/review contract.

Uses only configured Lezgi/Tsez development data and real .dproj workspaces.
Context is explicitly disabled to retain the frozen word-gloss baseline condition.
"""
import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from decipher.corpus_evaluate import file_info
from decipher.gloss_checkpoint import digest, encoded
from decipher.gloss_evaluate import GlossMetrics, provenance, select_online, write_json
from decipher.review import review_queue
from decipher.review_calibration import Calibration, build_calibration
from decipher.teaching import TeachingService
from decipher.project import LanguageProject
from decipher.workspace import WorkspaceStore


def run(language, directory, report_directory, *, training_sentences=110, calibration_sentences=100,
        limit_dev=None, review_budget=10, mode='rules'):
    if (type(training_sentences) is not int or training_sentences < 1
            or type(calibration_sentences) is not int or calibration_sentences < 1
            or type(review_budget) is not int or review_budget < 1
            or (limit_dev is not None and (type(limit_dev) is not int or limit_dev < 1))):
        raise ValueError('All sentence budgets and optional development limits must be positive integers')
    if language not in ('lezgi', 'tsez') or mode not in ('memory', 'analogy', 'rules'):
        raise ValueError('Use only Lezgi/Tsez development languages and an existing learner mode')
    directory, report_directory = Path(directory), Path(report_directory)
    for destination in (directory, report_directory):
        if destination.exists() and any(destination.iterdir()):
            raise ValueError(f'Refusing to overwrite existing artifacts: {destination}')
    configured = json.loads((ROOT/'data'/'glossing'/'SOURCES.json').read_text(encoding='utf-8'))[language]
    data_directory = ROOT/'data'/'glossing'/language
    for filename, source in configured['files'].items():
        if digest((data_directory/filename).read_bytes()) != source['sha256']:
            raise ValueError(f'Pinned source checksum mismatch: {filename}')
    prefix = 'lez' if language == 'lezgi' else 'ddo'
    train, dev = data_directory/f'{prefix}-train-track1-uncovered', data_directory/f'{prefix}-dev-track1-uncovered'
    roles, filters = select_online(train, dev, training_sentences, calibration_sentences)
    training, fit, validation = roles['support'], roles['stream'], roles['probes']
    if limit_dev is not None:
        validation = validation[:limit_dev]
    if not validation or len(validation) > 1000:
        raise ValueError('Review validation needs 1..1000 unique development sentences')
    directory.mkdir(parents=True, exist_ok=True)
    report_directory.mkdir(parents=True, exist_ok=True)
    origin = provenance()
    origin['product_implementation_sha256'] = {
        path.relative_to(ROOT).as_posix(): digest(path.read_text(encoding='utf-8').encode('utf-8'))
        for path in [ROOT/'decipher'/name for name in ('teaching.py', 'teaching_app.py', 'workspace.py', 'project.py', 'gloss_app.py', 'gloss_web.py', 'review.py', 'review_calibration.py')]
        +[Path(__file__).resolve()]}
    origin['no_third_party_site_packages'] = bool(sys.flags.no_site)
    store = WorkspaceStore()
    project_path = directory/'project.dproj'
    LanguageProject.create(project_path, f'{language} development review', language,
                           {'mode': mode, 'contextual': False})
    project = store.open(project_path)
    service = TeachingService(project)
    start = perf_counter()
    for gold in training:
        project.submit(gold.example)
        ticket = service.predict(gold.example.id)
        service.correct(ticket['prediction_id'], gold.glosses,
                        operation_id=f'seed:{gold.example.id}', reason='Explicit development training label')
    training_seconds = perf_counter()-start
    frozen_identity = project.model_identity()
    original_version = project.model_version
    before_predictions = {gold.example.id: project.predict(gold.example) for gold in validation}
    baseline = GlossMetrics()
    for gold in validation:
        baseline.add(gold, before_predictions[gold.example.id], project.workspace.model)
        project.submit(gold.example)
    project.save()
    start = perf_counter()
    calibration = build_calibration(project, fit, validation)
    calibration_seconds = perf_counter()-start
    calibration.manifest.update({'training_file': file_info(train), 'development_file': file_info(dev),
                                 'selection': 'Unique upstream prefix: learner training, then calibration; disjoint development validation',
                                 'filters': filters})
    calibration_path = directory/'calibration.json'
    calibration.save(calibration_path)
    restored_calibration = Calibration.load(calibration_path)
    assert encoded(restored_calibration.state()) == encoded(calibration.state())
    start = perf_counter()
    heuristic = review_queue(project, limit=len(validation))
    calibrated = review_queue(project, limit=len(validation), calibration=restored_calibration)
    queue_seconds = perf_counter()-start
    assert project.model_identity() == frozen_identity and project.model_version == original_version
    after_predictions = {gold.example.id: project.predict(gold.example) for gold in validation}
    assert encoded(before_predictions) == encoded(after_predictions)
    reopened = store.open(project_path)
    assert reopened.model_identity() == frozen_identity
    for gold in validation:
        assert reopened.annotation(gold.example.id) is None
    gold_by_id = {gold.example.id: gold for gold in validation}
    budget = min(review_budget, len(validation))
    def reviewed(ids):
        ids = ids[:budget]
        words = errors = sentence_errors = 0
        for identifier in ids:
            gold = gold_by_id[identifier]
            wrong = sum(word['gloss'] != target for word, target in zip(before_predictions[identifier], gold.glosses))
            words += len(gold.glosses)
            errors += wrong
            sentence_errors += wrong > 0
        return {'sentence_reviews': len(ids), 'word_annotations': words, 'incorrect_words_found': errors,
                'word_error_fraction': errors/words if words else None,
                'sentences_with_errors': sentence_errors, 'ids': ids}
    comparisons = {'upstream_order': reviewed([gold.example.id for gold in validation]),
                   'unknown_ambiguity_order': reviewed([row['id'] for row in heuristic['items']]),
                   'validated_calibration_or_fallback': reviewed([row['id'] for row in calibrated['items']])}
    for filename, values in (('validation-predictions.jsonl', [
            {'id': gold.example.id, 'tokens': list(gold.example.tokens), 'model_version': original_version,
             'words': before_predictions[gold.example.id]} for gold in validation]),
                            ('validation-gold.jsonl', [
            {'id': gold.example.id, 'glosses': list(gold.glosses)} for gold in validation])):
        (directory/filename).write_text(''.join(encoded(row).decode('utf-8')+'\n' for row in values), encoding='utf-8')
    write_json(directory/'review-queues.json', {'heuristic': heuristic, 'calibrated_or_fallback': calibrated})
    def membership(records):
        return {'sentences': len(records), 'word_labels': sum(len(gold.glosses) for gold in records),
                'selection': [{'id': gold.example.id, 'source_sha256': digest(encoded(gold.example.tokens))} for gold in records]}
    report = {'schema_version': 1, 'task': 'Frozen-model development correctness calibration and review ordering using production .dproj workspaces',
              'language': language, 'mode': mode, 'contextual': False, 'training': file_info(train), 'development': file_info(dev),
              'source_manifest': file_info(ROOT/'data'/'glossing'/'SOURCES.json'), 'filters': filters,
              'budgets': {'learner_training': membership(training), 'calibration_fit': membership(fit),
                          'calibration_validation': membership(validation)}, 'limit_dev': limit_dev,
              'model_version': original_version, 'model_identity': frozen_identity,
              'baseline_prediction_metrics': baseline.result(), 'calibration': calibration.state(),
              'review_comparison': comparisons,
              'read_only_checks': {'model_identity_unchanged': True, 'full_candidates_unchanged': True,
                                   'validation_answers_never_taught': True, 'workspace_reopen_matches': True,
                                   'calibration_reload_matches': True},
              'phase_seconds': {'training_and_workspace_io': training_seconds, 'calibration': calibration_seconds,
                                'two_review_queues': queue_seconds}, 'provenance': origin,
              'artifact_sha256': {name: digest((directory/name).read_bytes()) for name in
                                  ('project.dproj', 'calibration.json', 'validation-predictions.jsonl', 'validation-gold.jsonl', 'review-queues.json')},
              'limitations': ['Single ordered development prefix; no language-level significance claim',
                              'Calibration and validation labels are additional supervision, not learner training',
                              'Review compares equal sentence budgets; word annotation costs differ and are reported',
                              'Error concentration before teaching is not a measured learning gain',
                              'Uses A workspace persistence with B teaching/review adapter; no external user-trial claim',
                              'No internal-stem-edit experiment or default-model change']}
    write_json(directory/'results.json', report)
    write_json(report_directory/'results.json', report)
    status = calibration.status(frozen_identity)
    lines = [f'# {language.title()} review/calibration development check', '', report['task'], '',
             f"Mode: {mode}. Calibration status: **{status}**. Learner version: {original_version}.", '',
             '| Label purpose | Sentences | Word labels |', '|---|---:|---:|']
    for name, selected in report['budgets'].items():
        lines.append(f"| {name} | {selected['sentences']} | {selected['word_labels']} |")
    lines += ['', f"Frozen validation word accuracy: {report['baseline_prediction_metrics']['word_accuracy']:.2%}.",
              f"Estimate coverage: {calibration.validation['coverage']:.2%}; held-out ECE: {calibration.validation['estimated']['ece']}; "
              f"Brier: {calibration.validation['estimated']['brier']}; constant-prior Brier: {calibration.validation['constant_fit_prior']['brier']}.", '',
              '| Review order | Sentence reviews | Word annotations | Incorrect words found | Error fraction |', '|---|---:|---:|---:|---:|']
    for name, counts in comparisons.items():
        lines.append(f"| {name} | {counts['sentence_reviews']} | {counts['word_annotations']} | {counts['incorrect_words_found']} | {counts['word_error_fraction']:.2%} |")
    lines += ['', 'The learner received only its declared training labels. Calibration fitting and validation remained disjoint and frozen; '
              'all validation candidates and model identity are unchanged. Reopen and calibration reload checks passed. '
              'A failed calibration supplies no confidence estimates; the last row then uses the documented heuristic fallback.', '',
              'This is an ordered prefix development diagnostic. Equal sentence review budgets can cost different numbers of word annotations. '
              'It measures where errors concentrate before teaching, not subsequent learning or unrestricted translation. '
              'Raw artifacts stay in the specified local run directory; the workspace uses A\'s production format. '
              'Gitksan and the deferred stem-edit experiment are untouched.', '']
    (report_directory/'summary.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f"{language}: calibration {status}; validation word accuracy {report['baseline_prediction_metrics']['word_accuracy']:.2%}; "
          f"ECE {calibration.validation['estimated']['ece']}; frozen/reopen checks passed", flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language', choices=('lezgi', 'tsez'), required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--report-dir', type=Path, required=True)
    parser.add_argument('--training-sentences', type=int, default=110)
    parser.add_argument('--calibration-sentences', type=int, default=100)
    parser.add_argument('--limit-dev', type=int)
    parser.add_argument('--review-budget', type=int, default=10)
    parser.add_argument('--mode', choices=('memory', 'analogy', 'rules'), default='rules')
    args = parser.parse_args()
    try:
        run(args.language, args.run_dir, args.report_dir, training_sentences=args.training_sentences,
            calibration_sentences=args.calibration_sentences, limit_dev=args.limit_dev,
            review_budget=args.review_budget, mode=args.mode)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f'Review evaluation error: {exc}\n')


if __name__ == '__main__':
    main()
