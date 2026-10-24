"""Isolated, bounded full-development experiment for internal stem edits.

Default application models, CLI, metrics and checkpoints are never modified.
Use compare for each development language, tests for a persisted regression
record, and decide for the predeclared two-language adoption screen.
"""
from collections import Counter
import gc
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from time import perf_counter
import unittest
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from decipher.corpus_evaluate import file_info
from decipher.gloss import GlossLearner, lexical_key
from decipher.gloss_checkpoint import digest, encoded, _replace_with_retry
from decipher.gloss_evaluate import GlossMetrics, prepare
from decipher.gloss_internal import ALGORITHM_ID, InternalGlossOverlay
from decipher.teaching import learner_identity

BASELINE_COMMIT = 'bc0a5dff3b67c944a2696538d1f19a6b8eeb05da'
PROTOCOL_COMMIT = '9afb8b8'
PROTOCOL_PATH = 'plans/updates_b/feature-4/01-plan-and-frozen-protocol.md'
CONFIG = {'mode': 'rules', 'max_rules': 512, 'paradigm_window': 32, 'contextual': False,
          'unchanged_source_flanks': 1, 'minimum_shared_gloss_span': 2,
          'duplicate_record_policy': 'retain offline baseline weighting', 'split': 'dev'}
GATES = {'max_word_accuracy_loss': .005, 'min_mean_grounded_oov_gain': .01,
         'max_single_grounded_oov_loss': .005, 'prediction_ratio': 2.0,
         'prediction_absolute_extra_seconds': .25, 'max_peak_bytes': 512*1024*1024,
         'max_child_seconds': 120.0}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')+b'\n')
        _replace_with_retry(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()


def source_fingerprint():
    names = ('decipher/gloss.py', 'decipher/corpus.py', 'decipher/gloss_evaluate.py',
             'decipher/gloss_internal.py', 'tools/evaluate_internal_edits.py')
    return {name: digest((ROOT/name).read_text(encoding='utf-8').encode('utf-8')) for name in names}


def peak_memory():
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)]+[
                (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
                'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return {'peak_bytes': counters.PeakWorkingSetSize, 'api': 'Windows PROCESS_MEMORY_COUNTERS.PeakWorkingSetSize'}
    import resource
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {'peak_bytes': value*(1 if sys.platform == 'darwin' else 1024), 'api': 'resource.getrusage process ru_maxrss, converted to bytes'}


def bounded_child(command, timeout, *, cwd=None):
    if type(timeout) not in (int, float) or not 0 < timeout <= GATES['max_child_seconds']:
        raise ValueError('Child timeout must be positive and at most 120 seconds')
    start = perf_counter()
    try:
        result = subprocess.run(command, cwd=cwd, timeout=timeout, check=False)
        return {'status': 'exited', 'returncode': result.returncode, 'parent_elapsed_seconds': perf_counter()-start}
    except subprocess.TimeoutExpired:
        return {'status': 'timeout', 'returncode': None, 'parent_elapsed_seconds': perf_counter()-start}


def error_bucket(target, prediction):
    if prediction['gloss'] == target:
        return 'correct'
    if any(candidate['gloss'] == target for candidate in prediction['candidates'][:5]):
        return 'correct_gloss_below_top1'
    key = lexical_key(target)
    if key and any(lexical_key(candidate['gloss']) == key for candidate in prediction['candidates']):
        return 'grammatical_output_missing'
    return 'grounded_lexeme_not_recovered'


def score_pairs(golds, baseline, experimental, grounded_lexemes):
    if not len(golds) == len(baseline) == len(experimental):
        raise ValueError('Sentence predictions must align with the frozen scoring set')
    base_metric, internal_metric = GlossMetrics(), GlossMetrics()
    transitions, failures = Counter(), {'baseline': Counter(), 'experimental': Counter()}
    samples = {'improvements': [], 'regressions': [], 'grounded_failures': []}
    changed, known = [], {'words': 0, 'candidate_mismatches': 0}
    grounded = {tuple(key) for key in grounded_lexemes}
    for gold, before, after in zip(golds, baseline, experimental):
        base_metric.add(gold, before, grounded_lexemes=grounded)
        internal_metric.add(gold, after, grounded_lexemes=grounded)
        for index, (word, target, left, right) in enumerate(zip(gold.example.tokens, gold.glosses, before, after)):
            if left['known_form'] != right['known_form']:
                raise ValueError('The overlay cannot change training-vocabulary membership')
            first, second = left['gloss'] == target, right['gloss'] == target
            transitions[('both_correct' if second else 'baseline_correct_only') if first
                        else ('experimental_correct_only' if second else 'both_wrong')] += 1
            transitions['candidate_records_changed'] += left != right
            transitions['top_gloss_changed'] += left['gloss'] != right['gloss']
            transitions['newly_covered'] += left['gloss'] is None and right['gloss'] is not None
            transitions['lost_coverage'] += left['gloss'] is not None and right['gloss'] is None
            if left['known_form']:
                known['words'] += 1
                known['candidate_mismatches'] += left != right
                transitions['known_form_errors_unchanged'] += not first and not second
            key = lexical_key(target)
            grounded_oov = not left['known_form'] and bool(key) and key in grounded
            row = {'id': gold.example.id, 'word_index': index, 'word': word, 'expected': target,
                   'baseline': left, 'experimental': right, 'grounded_oov': grounded_oov}
            if grounded_oov:
                failures['baseline'][error_bucket(target, left)] += 1
                failures['experimental'][error_bucket(target, right)] += 1
                if not second and len(samples['grounded_failures']) < 25:
                    samples['grounded_failures'].append({**row, 'failure': error_bucket(target, right)})
            if left != right:
                changed.append(row)
                if not first and second and len(samples['improvements']) < 25:
                    samples['improvements'].append(row)
                if first and not second and len(samples['regressions']) < 25:
                    samples['regressions'].append(row)
    return {'baseline': base_metric.result(), 'experimental': internal_metric.result(),
            'transitions': dict(transitions), 'known_form_equality': known,
            'grounded_oov_failures': {name: dict(counts) for name, counts in failures.items()},
            'samples': samples}, changed


def _duplicates(records):
    first, count, conflicts = {}, 0, 0
    for record in records:
        source = record.example.tokens
        if source in first:
            count += 1
            conflicts += record.glosses != first[source]
        else:
            first[source] = record.glosses
    return {'repeated_whole_sources': count, 'conflicting_annotations': conflicts,
            'unique_sources': len(first), 'policy': 'retained equally in both systems'}


def worker(language, directory):
    directory = Path(directory)
    stage = 'source validation'
    report = {'schema_version': 1, 'status': 'running', 'language': language, 'algorithm_id': ALGORITHM_ID,
              'config': CONFIG, 'decision_criteria': GATES, 'timings': {}}
    def progress(value):
        nonlocal stage
        stage = value
        write_json(directory/'progress.json', {'phase': stage})
        print(f'{language}: {stage}', flush=True)
    try:
        progress(stage)
        fingerprint = source_fingerprint()
        frozen = subprocess.check_output(['git', 'show', f'{BASELINE_COMMIT}:decipher/gloss.py'], cwd=ROOT).decode('utf-8').replace('\r\n', '\n')
        if digest(frozen.encode('utf-8')) != fingerprint['decipher/gloss.py']:
            raise ValueError('Default learner differs from the frozen baseline revision')
        report['source'] = {'commit': git('rev-parse', 'HEAD'), 'branch': git('branch', '--show-current'),
                            'implementation_sha256': fingerprint, 'baseline_commit': BASELINE_COMMIT,
                            'protocol_commit': git('rev-parse', PROTOCOL_COMMIT),
                            'protocol_sha256': digest(subprocess.check_output(['git', 'show', f'{PROTOCOL_COMMIT}:{PROTOCOL_PATH}'], cwd=ROOT))}
        report['environment'] = {'python': sys.version, 'platform': platform.platform(), 'machine': platform.machine(),
                                 'processor': platform.processor(), 'no_site_packages': bool(sys.flags.no_site)}
        sources = json.loads((ROOT/'data/glossing/SOURCES.json').read_text(encoding='utf-8'))[language]
        folder = ROOT/'data/glossing'/language
        for filename, metadata in sources['files'].items():
            if digest((folder/filename).read_bytes()) != metadata['sha256']:
                raise ValueError(f'Pinned corpus checksum mismatch: {filename}')
        prefix = 'lez' if language == 'lezgi' else 'ddo'
        train, dev = folder/f'{prefix}-train-track1-uncovered', folder/f'{prefix}-dev-track1-uncovered'
        progress('parsing full training/development')
        start = perf_counter()
        training, golds, filters = prepare(train, dev)
        report['timings']['parsing_seconds'] = perf_counter()-start
        manifest = {'training': file_info(train), 'development': file_info(dev), 'filters': filters,
                    'source_metadata': sources, 'membership': {
                        name: [{'id': row.example.id, 'source_sha256': digest(encoded(row.example.tokens))} for row in records]
                        for name, records in (('training', training), ('development', golds))}}
        write_json(directory/'manifest.json', manifest)
        report['dataset'] = {'training': file_info(train), 'development': file_info(dev), 'filters': filters,
                             'training_sentences': len(training), 'training_word_labels': sum(len(row.glosses) for row in training),
                             'development_sentences': len(golds), 'development_words': sum(len(row.glosses) for row in golds),
                             'training_duplicates': _duplicates(training), 'development_duplicates': _duplicates(golds),
                             'manifest_sha256': digest(encoded(manifest))}
        progress('fitting frozen baseline')
        start = perf_counter()
        base = GlossLearner('rules', 512, 32, contextual=False).fit(training)
        report['timings']['base_fit_seconds'] = perf_counter()-start
        identity = learner_identity(base)
        report['memory_after_base'] = peak_memory()
        progress('preparing internal overlay')
        start = perf_counter()
        overlay = InternalGlossOverlay(base)
        report['timings']['overlay_prepare_seconds'] = perf_counter()-start
        report['rules'] = overlay.diagnostics()
        rule_state = [{'rule': list(rule), 'support': len(overlay._evidence[rule])} for rule in overlay.selected_rules]
        write_json(directory/'selected-rules.json', rule_state)
        rule_hash = digest(encoded(rule_state))
        progress('baseline prediction')
        start = perf_counter()
        baseline = [base.predict(row.example) for row in golds]
        report['timings']['baseline_prediction_seconds'] = perf_counter()-start
        progress('experimental prediction')
        start = perf_counter()
        experimental = [overlay.predict(row.example) for row in golds]
        report['timings']['experimental_prediction_seconds'] = perf_counter()-start
        progress('private scoring and grounded-error analysis')
        start = perf_counter()
        grounded = [list(key) for key in sorted(base.paradigms)]
        scored, changed = score_pairs(golds, baseline, experimental, grounded)
        report.update(scored)
        if scored['known_form_equality']['candidate_mismatches']:
            raise AssertionError('Known-form candidates changed')
        recovery_counts = Counter()
        for gold, predictions in zip(golds, experimental):
            for word, target, prediction in zip(gold.example.tokens, gold.glosses, predictions):
                key = lexical_key(target)
                if word in base.lexicon or not key or key not in base.paradigms or prediction['gloss'] == target:
                    continue
                recoveries = overlay.recoveries(word)
                recovered = any(lexical_key(gloss) == key for row in recoveries if row['rule'][0] == 'internal'
                                for anchor in row['anchors'] for gloss in base.lexicon[anchor])
                recovery_counts['internal_anchor_for_gold_lexeme' if recovered else 'no_selected_internal_anchor_for_gold_lexeme'] += 1
        report['grounded_error_recovery'] = dict(recovery_counts)
        for change in changed:
            if change['baseline']['gloss'] == change['expected'] and change['experimental']['gloss'] != change['expected']:
                candidates = change['baseline']['candidates']
                change['baseline_winning_rule_displaced'] = bool(candidates and candidates[0].get('rule')
                                                                 and tuple(candidates[0]['rule']) not in overlay.selected_rules)
        report['regression_winning_rules_displaced'] = sum(row.get('baseline_winning_rule_displaced', False) for row in changed)
        report['timings']['scoring_and_analysis_seconds'] = perf_counter()-start
        write_json(directory/'scoring-context.json', {'grounded_lexemes': grounded})
        for filename, rows in (
            ('predictions.jsonl', ({'id': row.example.id, 'tokens': list(row.example.tokens), 'baseline': left, 'experimental': right}
                                   for row, left, right in zip(golds, baseline, experimental))),
            ('private-gold.jsonl', ({'id': row.example.id, 'glosses': list(row.glosses)} for row in golds)),
            ('private-changes.jsonl', iter(changed))):
            with (directory/filename).open('w', encoding='utf-8') as handle:
                for row in rows:
                    handle.write(encoded(row).decode('utf-8')+'\n')
        if learner_identity(base) != identity:
            raise AssertionError('Experiment mutated the authoritative base model')
        progress('base checkpoint save and explicit reconstruction')
        start = perf_counter()
        base.save(directory/'base-model.json.gz')
        report['timings']['base_checkpoint_save_seconds'] = perf_counter()-start
        # Simulate a restart rather than holding two complete fitted rule graphs.
        del overlay, base
        gc.collect()
        start = perf_counter()
        restored = InternalGlossOverlay.from_checkpoint(directory/'base-model.json.gz')
        report['timings']['checkpoint_load_and_prepare_seconds'] = perf_counter()-start
        restored_rules = [{'rule': list(rule), 'support': len(restored._evidence[rule])} for rule in restored.selected_rules]
        if digest(encoded(restored_rules)) != rule_hash or learner_identity(restored.base) != identity:
            raise AssertionError('Checkpoint reconstruction changed model identity or selected rules')
        start = perf_counter()
        for gold, left, right in zip(golds, baseline, experimental):
            if restored.base.predict(gold.example) != left or restored.predict(gold.example) != right:
                raise AssertionError(f'Checkpoint changed full candidates: {gold.example.id}')
        report['timings']['reconstruction_verification_seconds'] = perf_counter()-start
        report['memory'] = {**peak_memory(), 'scope': 'Process lifetime peak: parsing, base plus overlay, output arrays and reconstruction; one fitted graph pair retained at a time'}
        report['checks'] = {'base_identity_unchanged': True, 'known_form_candidates_exact': True,
                            'checkpoint_full_candidates_exact': True, 'checkpoint_rules_exact': True,
                            'source_only_inputs': True, 'default_engine_source_matches_frozen_commit': True}
        report['artifact_sha256'] = {name: digest((directory/name).read_bytes()) for name in
                                    ('manifest.json', 'selected-rules.json', 'scoring-context.json', 'predictions.jsonl', 'private-gold.jsonl', 'private-changes.jsonl', 'base-model.json.gz')}
        report['status'] = 'complete'
        progress('complete')
    except Exception as exc:
        report.update(status='failed', incomplete_phase=stage, error=f'{type(exc).__name__}: {exc}')
        print(f'{language}: failed during {stage}: {exc}', flush=True)
    write_json(directory/'results.json', report)
    return report


def summarize(report, directory):
    directory = Path(directory)
    write_json(directory/'results.json', report)
    lines = [f"# Internal-edit experiment: {report['language']}", '', f"Status: **{report['status']}**.", '']
    if report['status'] == 'complete':
        lines += ['| System | Word exact | OOV | Grounded OOV | Coverage | Sentence exact |', '|---|---:|---:|---:|---:|---:|']
        for name in ('baseline', 'experimental'):
            result = report[name]
            def pct(key):
                return 'n/a' if result[key] is None else f'{result[key]:.3%}'
            lines.append('| '+name+' | '+' | '.join(pct(key) for key in ('word_accuracy', 'oov_accuracy', 'grounded_oov_accuracy', 'coverage', 'sentence_accuracy'))+' |')
        lines += ['', f"Rules: {report['rules']}. Time seconds: {report['timings']}.",
                  f"Process peak: {report['memory']['peak_bytes']} bytes ({report['memory']['peak_bytes']/1024**2:.2f} MiB).",
                  f"Correctness transitions: {report['transitions']}.", '',
                  'Both systems use the same full pinned training/development records and one 512-rule budget. '
                  'Duplicate-source weighting is retained and disclosed. These are development results, not unrestricted translation or language-level significance. '
                  'Scores remain uncalibrated. The default learner and production CLI/checkpoint schemas are unchanged. '
                  'A separate two-language decision report applies the preregistered adoption gates.', '']
    else:
        lines += [f"Incomplete phase: {report.get('incomplete_phase', 'unknown')}. {report.get('error', '')}",
                  'Incomplete runs are not counted as successful comparisons.', '']
    (directory/'summary.md').write_text('\n'.join(lines), encoding='utf-8')


def compare(language, directory, report_directory, timeout=120):
    directory, report_directory = Path(directory), Path(report_directory)
    for path in (directory, report_directory):
        if path.exists() and any(path.iterdir()):
            raise ValueError(f'Choose a fresh artifact directory: {path}')
    if not 0 < timeout <= 120:
        raise ValueError('Deadline must be positive and at most 120 seconds')
    directory.mkdir(parents=True, exist_ok=True)
    report_directory.mkdir(parents=True, exist_ok=True)
    result = bounded_child([sys.executable, '-X', 'utf8', '-S', str(Path(__file__).resolve()), 'compare',
                            '--language', language, '--run-dir', str(directory.resolve()), '--report-dir', str(report_directory.resolve()),
                            '--timeout', str(timeout), '--worker'], timeout, cwd=ROOT)
    try:
        report = json.loads((directory/'results.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        report = {'schema_version': 1, 'language': language, 'status': 'failed'}
    report['process'] = {**result, 'timeout_seconds': timeout,
                         'scope': 'subprocess execution timeout; platform process-start/cleanup overhead included in parent elapsed time'}
    if result['status'] == 'timeout':
        try:
            phase = json.loads((directory/'progress.json').read_text(encoding='utf-8'))['phase']
        except (OSError, ValueError, KeyError):
            phase = 'unknown'
        report.update(status='timeout', incomplete_phase=phase, error=f'Child exceeded {timeout:g}-second timeout')
    elif result['returncode'] != 0 and report['status'] == 'complete':
        report.update(status='failed', error=f"Worker exited with status {result['returncode']}")
    write_json(directory/'results.json', report)
    summarize(report, report_directory)
    return report


def run_tests(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Choose a fresh regression record path')
    before = source_fingerprint()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT/'tests')))
    record = {'schema_version': 1, 'successful': result.wasSuccessful(), 'tests_run': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
              'source_commit': git('rev-parse', 'HEAD'), 'implementation_sha256': before,
              'code_unchanged_during_tests': before == source_fingerprint(), 'python': sys.version}
    write_json(output, record)
    return record


def adoption_decision(reports, tests):
    complete = len(reports) == 2 and {row['language'] for row in reports} == {'lezgi', 'tsez'} and all(row['status'] == 'complete' for row in reports)
    checks = {'both_full_runs_complete': complete,
              'regressions_passed': bool(tests.get('successful') and tests.get('skipped') == 0 and tests.get('code_unchanged_during_tests'))}
    gains, per_language = [], []
    if complete:
        checks.update(same_tested_implementation=all(row['source']['implementation_sha256'] == tests['implementation_sha256'] for row in reports),
                      known_forms_exact=all(row['known_form_equality']['candidate_mismatches'] == 0 for row in reports),
                      checkpoint_reconstruction=all(row['checks']['checkpoint_full_candidates_exact'] and row['checks']['checkpoint_rules_exact'] for row in reports))
        for report in reports:
            base, experiment = report['baseline'], report['experimental']
            grounded_gain = (experiment['grounded_oov_accuracy']-base['grounded_oov_accuracy']
                             if experiment['grounded_oov_accuracy'] is not None and base['grounded_oov_accuracy'] is not None else None)
            word_gain = experiment['word_accuracy']-base['word_accuracy']
            initial = report['timings']['baseline_prediction_seconds']
            changed = report['timings']['experimental_prediction_seconds']
            values = {'language': report['language'], 'word_accuracy_gain_pp': 100*word_gain,
                      'grounded_oov_gain_pp': 100*grounded_gain if grounded_gain is not None else None,
                      'prediction_ratio': changed/initial if initial else None,
                      'prediction_extra_seconds': changed-initial, 'peak_bytes': report['memory']['peak_bytes'],
                      'word_accuracy_gate': word_gain >= -GATES['max_word_accuracy_loss'],
                      'grounded_oov_loss_gate': grounded_gain is not None and grounded_gain >= -GATES['max_single_grounded_oov_loss'],
                      'prediction_gate': changed <= 2*initial or changed-initial <= GATES['prediction_absolute_extra_seconds'],
                      'memory_gate': report['memory']['peak_bytes'] <= GATES['max_peak_bytes'],
                      'deadline_gate': report['process']['status'] == 'exited' and report['process']['returncode'] == 0
                                       and report['process']['timeout_seconds'] <= GATES['max_child_seconds']}
            if grounded_gain is not None:
                gains.append(grounded_gain)
            per_language.append(values)
        for name in ('word_accuracy_gate', 'grounded_oov_loss_gate', 'prediction_gate', 'memory_gate', 'deadline_gate'):
            checks[name] = all(row[name] for row in per_language)
        checks['mean_grounded_oov_gain'] = len(gains) == 2 and sum(gains)/2 >= GATES['min_mean_grounded_oov_gain']
    accepted = complete and all(checks.values())
    return {'schema_version': 1, 'decision': 'recommend_adoption_review' if accepted else 'reject_default_adoption',
            'default_changed': False, 'criteria': GATES, 'checks': checks,
            'failed_checks': [key for key, passed in checks.items() if not passed], 'per_language': per_language,
            'mean_grounded_oov_gain_pp': 100*sum(gains)/2 if len(gains) == 2 else None,
            'test_record': tests, 'note': 'Development screening only. Even passing requires separate default-model approval; no automatic promotion.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    compare_parser = commands.add_parser('compare')
    compare_parser.add_argument('--language', choices=('lezgi', 'tsez'), required=True)
    compare_parser.add_argument('--run-dir', type=Path, required=True)
    compare_parser.add_argument('--report-dir', type=Path, required=True)
    compare_parser.add_argument('--timeout', type=float, default=120)
    compare_parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    test_parser = commands.add_parser('tests')
    test_parser.add_argument('--output', type=Path, required=True)
    decision_parser = commands.add_parser('decide')
    decision_parser.add_argument('--reports', nargs=2, type=Path, required=True)
    decision_parser.add_argument('--tests', type=Path, required=True)
    decision_parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'compare':
            report = worker(args.language, args.run_dir) if args.worker else compare(args.language, args.run_dir, args.report_dir, args.timeout)
            return 0 if report['status'] == 'complete' else 2
        if args.command == 'tests':
            return 0 if run_tests(args.output)['successful'] else 2
        if args.output.exists():
            raise ValueError('Choose a new decision report path')
        reports = [json.loads(path.read_text(encoding='utf-8')) for path in args.reports]
        tests = json.loads(args.tests.read_text(encoding='utf-8'))
        decision = adoption_decision(reports, tests)
        decision['report_sha256'] = {str(path): digest(path.read_bytes()) for path in args.reports}
        decision['test_record_sha256'] = digest(args.tests.read_bytes())
        write_json(args.output, decision)
        print(json.dumps({key: decision[key] for key in ('decision', 'failed_checks', 'per_language')}, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        parser.exit(2, f'Internal-edit experiment error: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
