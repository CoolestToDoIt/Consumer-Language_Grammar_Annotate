"""Explicit development fixture for B's CLI contract; not A's workspace format.

Use only through the opt-in fixture backend. Storage owners should implement the
LanguageProject/ProjectStore contract with their production persistence.
"""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import uuid

from .corpus import TextExample
from .gloss import GlossLearner
from .gloss_checkpoint import digest, encoded, _replace_with_retry
from .teaching import (ProjectConflict, RevisionConflict, aligned_glosses, learner_identity,
                       public_example, validate_predictions)


def _atomic_json(path, value):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded(value))
        _replace_with_retry(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class FixtureProject:
    def __init__(self, path, *, name, language, mode='rules'):
        if not isinstance(name, str) or not name.strip() or not isinstance(language, str) or not language.strip():
            raise ValueError('Project name and language must be nonempty')
        self.path = Path(path)
        self.project_id = uuid.uuid4().hex
        self.name, self.language = name, language
        self.learner = GlossLearner(mode)
        self._sources, self._predictions, self._annotations = {}, {}, {}
        self._history, self._operations = [], {}
        self._disk_digest = None

    @property
    def model_version(self):
        return self.learner.version

    def submit(self, example):
        if not isinstance(example, TextExample):
            raise ValueError('Submit public TextExample records only')
        canonical = public_example(example.id, example.tokens)
        previous = self._sources.get(canonical.id)
        if previous is not None and previous != canonical:
            raise ValueError('An existing sentence ID cannot change source words')
        if previous is not None:
            return False
        self._sources[canonical.id] = canonical
        return True

    def examples(self):
        return tuple(self._sources.values())

    def predict(self, example):
        if not isinstance(example, TextExample):
            raise ValueError('Predict public source words only')
        canonical = public_example(example.id, example.tokens)
        return self.learner.predict(canonical)

    def remember_prediction(self, record):
        identifier = record['prediction_id']
        example = self._sources.get(record['example_id'])
        if not isinstance(identifier, str) or not identifier or example is None or list(example.tokens) != record['tokens']:
            raise ValueError('Prediction must identify a registered source sentence')
        if identifier in self._predictions:
            raise ValueError('Prediction IDs are immutable and cannot be reused')
        annotation = self.annotation(example.id)
        if (record['model_version'] != self.model_version or record['model_identity'] != self.model_identity()
                or record['annotation_revision'] != (annotation['revision'] if annotation else 0)):
            raise ValueError('Prediction metadata must describe the current project state')
        validate_predictions(record['words'], example.tokens)
        self._predictions[identifier] = copy.deepcopy(record)

    def prediction(self, identifier):
        if identifier not in self._predictions:
            raise ValueError(f'Unknown prediction ID: {identifier}; predict the sentence first')
        return copy.deepcopy(self._predictions[identifier])

    def annotation(self, identifier):
        return copy.deepcopy(self._annotations.get(identifier))

    def history(self, identifier):
        if identifier not in self._sources:
            raise ValueError(f'Unknown sentence ID: {identifier}')
        return tuple(copy.deepcopy(row) for row in self._history if row['example_id'] == identifier)

    def model_identity(self):
        return learner_identity(self.learner)

    def training_sources(self):
        return tuple(record.example.tokens for record in self.learner.records.values())

    def correct(self, prediction_id, glosses, *, expected_revision, operation_id, reason='', replace=False, confirm=False):
        before = self.prediction(prediction_id)
        example = self._sources[before['example_id']]
        values = aligned_glosses(glosses, example.tokens)
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError('Expected annotation revision must be a nonnegative integer')
        if not isinstance(operation_id, str) or not operation_id or len(operation_id) > 128:
            raise ValueError('Operation ID must be a nonempty string of at most 128 characters')
        if not isinstance(reason, str) or len(reason) > 2000 or type(replace) is not bool or type(confirm) is not bool:
            raise ValueError('Invalid correction reason or replacement/confirmation choice')
        request = {'prediction_id': prediction_id, 'glosses': list(values), 'expected_revision': expected_revision,
                   'operation_id': operation_id, 'reason': reason, 'replace': replace, 'confirm': confirm}
        previous_operation = self._operations.get(operation_id)
        if previous_operation is not None:
            if previous_operation['request'] != request:
                raise ValueError('An operation ID cannot be reused for a different correction')
            return copy.deepcopy(previous_operation['receipt'])
        current = self._annotations.get(example.id)
        revision = current['revision'] if current else 0
        if expected_revision != revision:
            raise RevisionConflict(f'Annotation changed: reviewed revision {expected_revision}, current revision {revision}. Reload and review it.')
        if confirm and (before['model_version'] != self.model_version or before['model_identity'] != self.model_identity()):
            raise RevisionConflict('Model changed since this prediction. Predict again before confirming.')
        if confirm and (any(word['gloss'] is None for word in before['words'])
                        or list(values) != [word['gloss'] for word in before['words']]):
            raise ValueError('Confirmation must exactly match a complete displayed prediction')
        changed = current is None or current['glosses'] != list(values)
        if changed and current is not None and (not replace or not reason.strip()):
            raise RevisionConflict('Replacing an existing different annotation needs an explicit replacement choice and reason')
        if changed:
            self.learner.correct(example, values)
            current = {'example_id': example.id, 'glosses': list(values), 'revision': revision+1,
                       'model_version': self.model_version, 'prediction_id': prediction_id,
                       'operation_id': operation_id, 'reason': reason,
                       'action': 'confirm' if confirm else 'correct',
                       'timestamp': datetime.now(timezone.utc).isoformat()}
            self._annotations[example.id] = current
            self._history.append(copy.deepcopy(current))
        receipt = {'example_id': example.id, 'revision': current['revision'], 'changed': changed,
                   'model_version': self.model_version, 'operation_id': operation_id}
        self._operations[operation_id] = {'request': request, 'receipt': receipt}
        return copy.deepcopy(receipt)

    def _state(self):
        return {'fixture_schema_version': 1, 'fixture_only': True, 'project_id': self.project_id,
                'name': self.name, 'language': self.language, 'mode': self.learner.mode,
                'model_version': self.model_version,
                'sources': [{'id': row.id, 'tokens': list(row.tokens)} for row in self.examples()],
                'predictions': list(copy.deepcopy(self._predictions).values()),
                'history': copy.deepcopy(self._history), 'operations': copy.deepcopy(self._operations)}

    def _envelope(self):
        state = self._state()
        return {'fixture_schema_version': 1, 'sha256': digest(encoded(state)), 'project': state}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_name(self.path.name+'.lock')
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ProjectConflict('This fixture is being saved by another process. Retry after it finishes; a lock left after a crash needs explicit recovery.') from exc
        try:
            current = digest(self.path.read_bytes()) if self.path.exists() else None
            if current != self._disk_digest:
                raise ProjectConflict('Another client saved this fixture. Reload before saving your changes.')
            envelope = self._envelope()
            _atomic_json(self.path, envelope)
            self._disk_digest = digest(encoded(envelope))
        finally:
            os.close(descriptor)
            lock.unlink(missing_ok=True)

    def export(self, path):
        destination = Path(path)
        if destination.exists():
            raise ValueError('Export destination already exists; choose a new path')
        destination.parent.mkdir(parents=True, exist_ok=True)
        _atomic_json(destination, self._envelope())


class FixtureProjectStore:
    """Single-user development storage, explicitly selected with --backend fixture."""
    def create(self, path, *, name, language, mode='rules'):
        path = Path(path)
        if path.exists():
            raise ValueError('Project already exists; open it instead')
        project = FixtureProject(path, name=name, language=language, mode=mode)
        project.save()
        return project

    def open(self, path):
        path = Path(path)
        try:
            content = path.read_bytes()
            envelope = json.loads(content)
            state = envelope['project']
            if (type(envelope.get('fixture_schema_version')) is not int or envelope['fixture_schema_version'] != 1
                    or state.get('fixture_schema_version') != 1 or state.get('fixture_only') is not True
                    or digest(encoded(state)) != envelope['sha256']):
                raise ValueError('Unsupported or corrupted fixture project')
            project = FixtureProject(path, name=state['name'], language=state['language'], mode=state['mode'])
            if not isinstance(state['project_id'], str) or not state['project_id']:
                raise ValueError('Invalid fixture identity')
            project.project_id = state['project_id']
            for source in state['sources']:
                if not project.submit(public_example(source['id'], source['tokens'])):
                    raise ValueError('Duplicate source ID in fixture project')
            for record in state['predictions']:
                example = project._sources[record['example_id']]
                if (record['prediction_id'] in project._predictions or record['tokens'] != list(example.tokens)
                        or type(record['model_version']) is not int or not 0 <= record['model_version'] <= state['model_version']
                        or type(record['annotation_revision']) is not int or record['annotation_revision'] < 0):
                    raise ValueError('Invalid stored prediction metadata')
                validate_predictions(record['words'], example.tokens)
                project._predictions[record['prediction_id']] = copy.deepcopy(record)
            # Reconstruct every revision in order, then verify the operation audit.
            for entry in state['history']:
                operation = state['operations'][entry['operation_id']]
                request = operation['request']
                if request['operation_id'] != entry['operation_id']:
                    raise ValueError('Inconsistent correction operation ID')
                receipt = project.correct(**request)
                if receipt != operation['receipt'] or project._history[-1] != dict(entry, timestamp=project._history[-1]['timestamp']):
                    raise ValueError('Annotation history differs from its authoritative correction operations')
                # Preserve original user-visible timestamps; do not replace history on open.
                project._history[-1] = copy.deepcopy(entry)
                project._annotations[entry['example_id']] = copy.deepcopy(entry)
            for identifier, operation in state['operations'].items():
                if identifier in project._operations:
                    continue
                request, receipt = operation['request'], operation['receipt']
                if (request['operation_id'] != identifier or receipt['operation_id'] != identifier
                        or receipt['changed'] is not False or request['prediction_id'] not in project._predictions
                        or receipt['example_id'] not in project._sources):
                    raise ValueError('Invalid idempotent correction receipt')
                project._operations[identifier] = copy.deepcopy(operation)
            if project.model_version != state['model_version']:
                raise ValueError('Fixture model version differs from annotation history')
            project._disk_digest = digest(content)
            return project
        except (KeyError, TypeError, AttributeError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f'Invalid fixture project: {exc}') from exc
