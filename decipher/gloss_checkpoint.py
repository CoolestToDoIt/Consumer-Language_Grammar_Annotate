"""Atomic, checksummed gloss sessions without importing the neural runtime."""
import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import zipfile

from .corpus import TextExample
from .gloss import GlossLearner
from .online import OnlineSession

SCHEMA_VERSION = 1
ALGORITHM_ID = 'source-only-gloss-stream-v1'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def digest(content):
    return hashlib.sha256(content).hexdigest()


def implementation_fingerprint():
    root = Path(__file__).parent
    return {name: digest((root/name).read_bytes()) for name in
            ('gloss.py', 'corpus.py', 'online.py', 'gloss_checkpoint.py', 'gloss_evaluate.py')}


def words(text, labels=False):
    values = json.loads(text)
    if not isinstance(values, list) or not values or any(
            not isinstance(word, str) or not word or any(c.isspace() for c in word)
            for word in values):
        raise ValueError('Expected a nonempty JSON list of word glosses' if labels else
                         'Expected a nonempty JSON list of source words')
    return tuple(values)


class GlossAdapter:
    """Only public words reach prediction; labels enter through correction."""
    def __init__(self, mode='rules', max_rules=512, paradigm_window=32, learner=None):
        self.learner = learner if learner is not None else GlossLearner(mode, max_rules, paradigm_window)
        self.config = SimpleNamespace(max_source_bytes=1000000, max_target_bytes=1000000)

    @property
    def version(self):
        return self.learner.version

    def predict(self, source, **kwargs):
        predictions = self.learner.predict(TextExample('input', words(source)))
        return {'text': json.dumps([p['gloss'] for p in predictions], ensure_ascii=False, separators=(',', ':')),
                'word_predictions': predictions,
                'grounded_lexemes': [list(key) for key in sorted(self.learner.paradigms)],
                'candidates': [], 'recall': False, 'version': self.version}

    def validate_source(self, source):
        words(source)

    def validate_feedback(self, source, target):
        if len(words(source)) != len(words(target, labels=True)):
            raise ValueError('Feedback glosses must align with source words')

    def correct(self, identifier, source, target):
        self.validate_feedback(source, target)
        return self.learner.correct(TextExample(identifier, words(source)), words(target, labels=True))


def _integer(value):
    return type(value) is int and value >= 0


def _validate_session(state, learner):
    """Replay the audit trail privately; never apply labels to an invalid restore."""
    if state.get('schema_version') != 1 or not _integer(state.get('step')):
        raise ValueError('Unsupported or invalid online session schema/step')
    if not isinstance(state.get('language_id'), str) or not isinstance(state.get('events'), list):
        raise ValueError('Invalid session identity/events')
    audit = GlossAdapter(learner.mode, learner.max_rules, learner.paradigm_window)
    sources, pending, processed = {}, [], {}
    count, previous_step = 0, 0
    fields = ('example_id', 'target', 'arrival_step', 'feedback_revision')
    for event in state['events']:
        step = event.get('step')
        if (event.get('schema_version') != 1 or event.get('language_id') != state['language_id']
                or not _integer(step) or not previous_step <= step <= count+1):
            raise ValueError('Invalid session event order or identity')
        previous_step = step
        kind, identifier = event['event_type'], event.get('example_id')
        if kind == 'prediction':
            if (step != count+1 or not isinstance(identifier, str) or not identifier
                    or identifier in sources or any(p['arrival_step'] <= step for p in pending)):
                raise ValueError('Invalid prediction order or unprocessed due answers')
            # JSON changes tuples to lists; compare canonical content.
            expected = audit.predict(event['source'])
            if encoded(expected) != encoded(event['prediction']) or event['model_version'] != audit.version:
                raise ValueError('Historical prediction/model version does not match its feedback history')
            sources[identifier] = event['source']
            count += 1
        elif kind == 'feedback_requested':
            if identifier not in sources or step != count:
                raise ValueError('Feedback request must follow its prediction')
            audit.validate_feedback(sources[identifier], event['target'])
            if not _integer(event['arrival_step']) or event['arrival_step'] < step or not _integer(event['feedback_revision']):
                raise ValueError('Invalid requested arrival/revision')
            latest = next((p for p in pending if p['example_id'] == identifier), processed.get(identifier))
            if latest and event['feedback_revision'] <= latest['feedback_revision']:
                raise ValueError('Duplicate or stale request in event history')
            pending = [p for p in pending if p['example_id'] != identifier]
            pending.append({key: event[key] for key in fields})
        elif kind == 'feedback':
            due = sorted((p for p in pending if p['arrival_step'] <= step), key=lambda p: p['arrival_step'])
            incoming = {key: event[key] for key in fields}
            if not due or incoming != due[0]:
                raise ValueError('Feedback arrival order differs from the requested schedule')
            changed = audit.correct(identifier, sources[identifier], event['target'])
            if event['model_version'] != audit.version or event.get('changed') != changed:
                raise ValueError('Feedback model version/change flag is inconsistent')
            processed[identifier] = incoming
            pending.remove(incoming)
        elif kind == 'teacher_decision':
            if identifier not in sources or step != count or type(event.get('requested')) is not bool:
                raise ValueError('Invalid teacher decision')
        else:
            raise ValueError('Unsupported gloss event type')
        if 'latency_ms' in event and (not isinstance(event['latency_ms'], (int, float))
                                     or not math.isfinite(event['latency_ms']) or event['latency_ms'] < 0):
            raise ValueError('Invalid event latency')
    if (count != state['step'] or sources != state['sources'] or pending != state['pending']
            or processed != state['processed'] or any(p['arrival_step'] <= count for p in pending)):
        raise ValueError('Session sources, cursor, pending or processed state disagrees with history')
    if (audit.learner.records != learner.records or list(audit.learner.records) != list(learner.records)
            or audit.version != learner.version):
        raise ValueError('Authoritative gloss model disagrees with feedback history')


def save_gloss_checkpoint(path, session, experiment):
    """One atomic ZIP contains the model, original history and experiment state."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as directory:
        directory = Path(directory)
        model_path = directory/'model.json.gz'
        session.learner.learner.save(model_path)
        components = {'model.json.gz': model_path.read_bytes(),
                      'session.json': encoded(session.state()), 'experiment.json': encoded(experiment)}
        integrity = {'schema_version': SCHEMA_VERSION, 'algorithm_id': ALGORITHM_ID,
                     'sha256': {name: digest(data) for name, data in components.items()}}
        temporary = directory/'checkpoint.zip'
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in components.items():
                archive.writestr(name, data)
            archive.writestr('integrity.json', encoded(integrity))
        temporary.replace(destination)


def load_gloss_checkpoint(path):
    """Reject incomplete, corrupted and incompatible data before returning state."""
    try:
        with zipfile.ZipFile(path) as archive:
            required = {'integrity.json', 'model.json.gz', 'session.json', 'experiment.json'}
            if len(archive.namelist()) != len(required) or set(archive.namelist()) != required:
                raise ValueError('Incomplete or unexpected checkpoint components')
            integrity = json.loads(archive.read('integrity.json'))
            if integrity.get('schema_version') != SCHEMA_VERSION or integrity.get('algorithm_id') != ALGORITHM_ID:
                raise ValueError('Unsupported gloss experiment checkpoint schema/algorithm')
            components = {name: archive.read(name) for name in required-{'integrity.json'}}
            if integrity['sha256'] != {name: digest(data) for name, data in components.items()}:
                raise ValueError('Checkpoint component checksum mismatch')
        state = json.loads(components['session.json'])
        experiment = json.loads(components['experiment.json'])
        if experiment.get('schema_version') != SCHEMA_VERSION:
            raise ValueError('Unsupported experiment schema')
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory)/'model.json.gz'
            model_path.write_bytes(components['model.json.gz'])
            learner = GlossLearner.load(model_path)
        _validate_session(state, learner)
        session = OnlineSession(GlossAdapter(learner=learner), state['language_id'])
        for key in ('step', 'sources', 'events', 'pending', 'processed'):
            setattr(session, key, copy.deepcopy(state[key]))
        # A late import avoids coupling model/session persistence to metric code.
        from .gloss_evaluate import validate_experiment
        validate_experiment(experiment, session)
        return session, experiment
    except (OSError, zipfile.BadZipFile, EOFError, KeyError, TypeError, AttributeError,
            json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError(f'Invalid gloss checkpoint: {exc}') from exc
