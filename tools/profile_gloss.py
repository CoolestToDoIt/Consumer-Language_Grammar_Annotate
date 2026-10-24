"""Bounded gloss-engine profiling and exact candidate-output regression checks.

This script deliberately calls the model directly; production evaluators and
CLI orchestration belong to the separate evaluation workstream.
"""
import argparse
import cProfile
from contextlib import contextmanager
import hashlib
from itertools import zip_longest
import json
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import tempfile
import time

# Support direct execution without requiring an editable installation.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from decipher.gloss import GlossLearner, load_gloss


class ProfiledGlossLearner(GlossLearner):
    def __init__(self, *args, **kwargs):
        self.profile = {'ingestion_seconds': 0.0, 'ranking_seconds': 0.0, 'ranking_passes': 0}
        super().__init__(*args, **kwargs)

    def _observe(self, record):
        start = time.perf_counter()
        try:
            return super()._observe(record)
        finally:
            self.profile['ingestion_seconds'] += time.perf_counter() - start

    def _rules(self):
        dirty = self._rule_cache is None
        start = time.perf_counter()
        try:
            return super()._rules()
        finally:
            if dirty:
                self.profile['ranking_seconds'] += time.perf_counter() - start
                self.profile['ranking_passes'] += 1


class ProfileTimeout(Exception):
    pass


@contextmanager
def deadline(seconds):
    if seconds <= 0:
        raise ValueError('Timeout must be positive')
    def expired(*_):
        raise ProfileTimeout(f'Exceeded {seconds:g}-second profiling deadline')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def git_identity():
    def git(*args):
        result = subprocess.run(['git', *args], cwd=ROOT, text=True, capture_output=True, check=True)
        return result.stdout.strip()
    return {'commit': git('rev-parse', 'HEAD'), 'branch': git('branch', '--show-current'),
            'tracked_dirty': bool(git('status', '--porcelain', '--untracked-files=no')),
            'engine_sha256': file_hash(ROOT / 'decipher/gloss.py')}


def peak_rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train', required=True)
    parser.add_argument('--dev', required=True)
    parser.add_argument('--strategy', choices=('sequential', 'bulk'), default='sequential')
    parser.add_argument('--mode', choices=('memory', 'analogy', 'rules'), default='rules')
    parser.add_argument('--prediction-modes', nargs='+', choices=('memory', 'analogy', 'rules'), default=('memory', 'analogy', 'rules'))
    parser.add_argument('--limit-train', type=int)
    parser.add_argument('--limit-dev', type=int)
    parser.add_argument('--max-rules', type=int, default=512)
    parser.add_argument('--paradigm-window', type=int, default=32)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--output', required=True)
    parser.add_argument('--predictions', required=True, help='Local JSONL candidate outputs, normally under ignored runs/')
    parser.add_argument('--reference-predictions')
    parser.add_argument('--cprofile', help='Optional binary profiling artifact, normally under ignored runs/')
    args = parser.parse_args(argv)
    for field in ('limit_train', 'limit_dev'):
        value = getattr(args, field)
        if value is not None and value < 1:
            parser.error(f'{field} must be positive')
    destination, predictions_path = Path(args.output), Path(args.predictions)
    destination.parent.mkdir(parents=True, exist_ok=True)
    predictions_path.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or predictions_path.exists():
        parser.error('Use new output and prediction paths; profiling never overwrites a baseline')
    report = {'status': 'running', 'config': vars(args), 'source': git_identity(),
              'environment': {'python': sys.version, 'platform': platform.platform(), 'machine': platform.machine()},
              'inputs': {name: {'path': str(path), 'sha256': file_hash(path)} for name, path in (('train', args.train), ('development', args.dev))}}
    model = None
    stage = 'parsing'
    profiler = cProfile.Profile() if args.cprofile else None
    try:
        with deadline(args.timeout):
            start = time.perf_counter()
            training, train_reader = load_gloss(args.train, skip_misaligned=True)
            development, dev_reader = load_gloss(args.dev, skip_misaligned=True)
            if args.limit_train:
                training = training[:args.limit_train]
            train_sources = {record.example.tokens for record in training}
            probes = [record for record in development if record.example.tokens not in train_sources]
            excluded = len(development) - len(probes)
            if args.limit_dev:
                probes = probes[:args.limit_dev]
            report['parsing_seconds'] = time.perf_counter() - start
            if not training or not probes:
                raise ValueError('Need nonempty training and nonoverlapping development inputs')
            report['dataset'] = {'training_sentences': len(training), 'training_words': sum(len(r.example.tokens) for r in training),
                                 'probe_sentences': len(probes), 'probe_words': sum(len(r.example.tokens) for r in probes),
                                 'excluded_train_source_overlap': excluded, 'training_reader': train_reader, 'development_reader': dev_reader,
                                 'training_ids_sha256': hashlib.sha256(json.dumps([r.example.id for r in training]).encode()).hexdigest(),
                                 'probe_ids_sha256': hashlib.sha256(json.dumps([r.example.id for r in probes]).encode()).hexdigest()}
            model = ProfiledGlossLearner(args.mode, args.max_rules, args.paradigm_window)
            stage = 'training'
            start = time.perf_counter()
            if profiler:
                profiler.enable()
            try:
                if args.strategy == 'bulk':
                    model.fit(iter(training))
                else:
                    for record in training:
                        model.correct(record.example, record.glosses)
            finally:
                if profiler:
                    profiler.disable()
            report['training_seconds'] = time.perf_counter() - start
            report['training_profile'] = dict(model.profile)
            report['model'] = {'version': model.version, 'authoritative_records': len(model.records), 'lexicon_forms': len(model.lexicon),
                               'rule_hypotheses': len(model.rule_evidence), 'prepared_rules': len(model._rules())}
            stage = 'prediction'
            prediction_digest = hashlib.sha256()
            report['prediction'] = {}
            with predictions_path.open('w', encoding='utf-8') as handle:
                for mode in args.prediction_modes:
                    model.mode = mode
                    correct, count = 0, 0
                    start = time.perf_counter()
                    for record in probes:
                        predictions = model.predict(record.example)
                        row = {'mode': mode, 'id': record.example.id, 'tokens': list(record.example.tokens), 'predictions': predictions}
                        line = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
                        handle.write(line)
                        prediction_digest.update(line.encode('utf-8'))
                        count += len(record.glosses)
                        correct += sum(p['gloss'] == target for p, target in zip(predictions, record.glosses))
                    report['prediction'][mode] = {'seconds': time.perf_counter() - start, 'correct_words': correct,
                                                  'words': count, 'word_accuracy': correct / count}
            report['predictions_sha256'] = prediction_digest.hexdigest()
            if args.reference_predictions:
                stage = 'reference comparison'
                with Path(args.reference_predictions).open(encoding='utf-8') as reference, predictions_path.open(encoding='utf-8') as actual:
                    for number, (left, right) in enumerate(zip_longest(reference, actual), 1):
                        if left is None or right is None or json.loads(left) != json.loads(right):
                            raise AssertionError(f'Full prediction/candidate mismatch at record {number}')
                report['reference_predictions'] = {'path': args.reference_predictions, 'sha256': file_hash(args.reference_predictions), 'exact_match': True}
            model.mode = args.mode
            stage = 'checkpoint save'
            with tempfile.TemporaryDirectory(prefix='gloss-engine-profile-') as tmp:
                checkpoint = Path(tmp) / 'model.json.gz'
                start = time.perf_counter()
                model.save(checkpoint)
                report['checkpoint_save_seconds'] = time.perf_counter() - start
                report['checkpoint_bytes'] = checkpoint.stat().st_size
                stage = 'checkpoint reload'
                start = time.perf_counter()
                restored = ProfiledGlossLearner.load(checkpoint)
                report['checkpoint_load_seconds'] = time.perf_counter() - start
                report['reload_profile'] = dict(restored.profile)
                if model.records != restored.records or model.version != restored.version or model._rules() != restored._rules():
                    raise AssertionError('Checkpoint changed authoritative records, version, or rule ordering')
                # Verify the entire local prediction artifact after reload as well.
                stage = 'reloaded prediction verification'
                with predictions_path.open(encoding='utf-8') as handle:
                    for line in handle:
                        row = json.loads(line)
                        restored.mode = row['mode']
                        from decipher.corpus import TextExample
                        actual = restored.predict(TextExample(row['id'], tuple(row['tokens'])))
                        if actual != row['predictions']:
                            raise AssertionError(f'Reloaded candidate mismatch: {row["id"]}')
                report['reloaded_predictions_exact_match'] = True
            report['status'] = 'complete'
    except ProfileTimeout as exc:
        report.update(status='timed_out', incomplete_stage=stage, error=str(exc))
        if model is not None:
            report['partial_training_profile'] = dict(model.profile)
            report['partial_authoritative_records'] = len(model.records)
    except Exception as exc:
        report.update(status='failed', incomplete_stage=stage, error=f'{type(exc).__name__}: {exc}')
    finally:
        report['process_peak_rss_bytes'] = peak_rss()
        if profiler:
            profile_path = Path(args.cprofile)
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            profiler.dump_stats(profile_path)
        destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report.get(key) for key in ('status', 'training_seconds', 'training_profile', 'checkpoint_load_seconds', 'predictions_sha256', 'error')}, indent=2), flush=True)
    return 0 if report['status'] == 'complete' else 2


if __name__ == '__main__':
    raise SystemExit(main())
