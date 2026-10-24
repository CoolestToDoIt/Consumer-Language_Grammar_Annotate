"""Teaching/review adapter for A's production .dproj workspace.

The authoritative model, annotations, save and export remain in project.py.
Teaching audit records live in one optional metadata field in the same project,
so a correction and its retry/history information commit atomically.
"""
import copy
import json
from pathlib import Path

from .corpus import TextExample
from .project import (LanguageProject, AnnotationRevisionConflict, ProjectWriteConflict)
from .teaching import (ProjectConflict, RevisionConflict, aligned_glosses, learner_identity,
                       public_example, validate_predictions)


def _revision_key(identifier, revision):
    return json.dumps([identifier, revision], ensure_ascii=False, separators=(',', ':'))


class WorkspaceProject:
    def __init__(self, workspace):
        self.workspace = workspace
        metadata = workspace.data.setdefault('teaching', {'schema_version': 1, 'predictions': {},
                                                         'operations': {}, 'revision_details': {}})
        if (not isinstance(metadata, dict) or type(metadata.get('schema_version')) is not int
                or metadata['schema_version'] != 1
                or any(not isinstance(metadata.get(key), dict) for key in ('predictions', 'operations', 'revision_details'))):
            raise ValueError('Unsupported teaching metadata in workspace')
        self._metadata = metadata
        self._validate_metadata()

    @property
    def path(self):
        return self.workspace.path

    @property
    def project_id(self):
        return self.workspace.data['project_id']

    @property
    def name(self):
        return self.workspace.data['name']

    @property
    def language(self):
        return self.workspace.data['language_id']

    @property
    def model_version(self):
        return self.workspace.model.version

    def _validate_metadata(self):
        try:
            sources = {example.id: example for example in self.examples()}
            for identifier, record in self._metadata['predictions'].items():
                example = sources[record['example_id']]
                annotation = self.annotation(example.id)
                if (not isinstance(identifier, str) or not identifier or record['prediction_id'] != identifier
                        or record['tokens'] != list(example.tokens)
                        or type(record['model_version']) is not int or not 0 <= record['model_version'] <= self.model_version
                        or type(record['annotation_revision']) is not int
                        or not 0 <= record['annotation_revision'] <= (annotation['revision'] if annotation else 0)
                        or not isinstance(record['model_identity'], str) or not record['model_identity']):
                    raise ValueError('Invalid stored teaching prediction metadata')
                validate_predictions(record['words'], example.tokens)
            for identifier, operation in self._metadata['operations'].items():
                request, receipt = operation['request'], operation['receipt']
                prediction = self._metadata['predictions'][request['prediction_id']]
                annotation = self.annotation(prediction['example_id'])
                if (request['operation_id'] != identifier or receipt['operation_id'] != identifier
                        or type(receipt['changed']) is not bool or annotation is None
                        or receipt['example_id'] != prediction['example_id']
                        or type(receipt['revision']) is not int or not 1 <= receipt['revision'] <= annotation['revision']
                        or type(receipt['model_version']) is not int or not 0 <= receipt['model_version'] <= self.model_version):
                    raise ValueError('Invalid stored correction receipt')
                aligned_glosses(request['glosses'], prediction['tokens'])
            for key, details in self._metadata['revision_details'].items():
                identifier, revision = json.loads(key)
                annotation = self.annotation(identifier)
                if (annotation is None or type(revision) is not int or not 1 <= revision <= annotation['revision']
                        or not isinstance(details.get('reason'), str)
                        or details.get('prediction_id') not in self._metadata['predictions']
                        or details.get('operation_id') not in self._metadata['operations']
                        or details.get('action') not in ('confirm', 'correct')):
                    raise ValueError('Invalid teaching revision details')
        except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
            raise ValueError(f'Invalid teaching metadata: {exc}') from exc

    def submit(self, example):
        canonical = public_example(example.id, example.tokens)
        return self.workspace.submit(canonical, persist=False)

    def examples(self):
        return tuple(TextExample(row['id'], tuple(row['tokens'])) for row in self.workspace.data['sentences'])

    def predict(self, example):
        if not isinstance(example, TextExample):
            raise ValueError('Predict public source examples only')
        return self.workspace.model.predict(public_example(example.id, example.tokens))

    def remember_prediction(self, record):
        example = self.workspace.sentence(record['example_id'])
        identifier = record['prediction_id']
        annotation = self.annotation(record['example_id'])
        if (not isinstance(identifier, str) or not identifier or identifier in self._metadata['predictions']
                or record['tokens'] != example['tokens'] or record['model_version'] != self.model_version
                or record['model_identity'] != self.model_identity()
                or record['annotation_revision'] != (annotation['revision'] if annotation else 0)):
            raise ValueError('Prediction must be new and describe the current source/model/annotation')
        validate_predictions(record['words'], example['tokens'])
        self._metadata['predictions'][identifier] = copy.deepcopy(record)

    def prediction(self, identifier):
        if identifier not in self._metadata['predictions']:
            raise ValueError('Unknown prediction ID; predict the sentence first')
        return copy.deepcopy(self._metadata['predictions'][identifier])

    def history(self, identifier):
        self.workspace.sentence(identifier)
        result = []
        for index, entry in enumerate(self.workspace.data['annotation_history'], 1):
            if entry['id'] == identifier:
                details = self._metadata['revision_details'].get(_revision_key(identifier, entry['revision']), {})
                result.append({'example_id': identifier, 'glosses': list(entry['glosses']), 'revision': entry['revision'],
                               'model_version': index, 'timestamp': entry['timestamp'],
                               'prediction_id': details.get('prediction_id'), 'operation_id': details.get('operation_id'),
                               'reason': details.get('reason', 'Imported or reviewed through the workspace'),
                               'action': details.get('action', 'workspace')})
        return tuple(result)

    def annotation(self, identifier):
        entries = self.history(identifier)
        return copy.deepcopy(entries[-1]) if entries else None

    def model_identity(self):
        return learner_identity(self.workspace.model)

    def training_sources(self):
        return tuple(row.example.tokens for row in self.workspace.model.records.values())

    def correct(self, prediction_id, glosses, *, expected_revision, operation_id, reason='', replace=False, confirm=False):
        before = self.prediction(prediction_id)
        values = aligned_glosses(glosses, before['tokens'])
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError('Expected annotation revision must be a nonnegative integer')
        if not isinstance(operation_id, str) or not operation_id or len(operation_id) > 128:
            raise ValueError('Operation ID must be a nonempty string of at most 128 characters')
        if not isinstance(reason, str) or len(reason) > 2000 or type(replace) is not bool or type(confirm) is not bool:
            raise ValueError('Invalid correction reason or replacement/confirmation choice')
        request = {'prediction_id': prediction_id, 'glosses': list(values), 'expected_revision': expected_revision,
                   'operation_id': operation_id, 'reason': reason, 'replace': replace, 'confirm': confirm}
        previous = self._metadata['operations'].get(operation_id)
        if previous is not None:
            if previous['request'] != request:
                raise ValueError('An operation ID cannot be reused for a different correction')
            return copy.deepcopy(previous['receipt'])
        current = self.annotation(before['example_id'])
        revision = current['revision'] if current else 0
        if revision != expected_revision:
            raise RevisionConflict(f'Annotation changed: reviewed revision {expected_revision}, current revision {revision}. Reload and review it.')
        if confirm and (before['model_version'] != self.model_version or before['model_identity'] != self.model_identity()):
            raise RevisionConflict('Model changed since this prediction. Predict again before confirming.')
        if confirm and (any(word['gloss'] is None for word in before['words'])
                        or list(values) != [word['gloss'] for word in before['words']]):
            raise ValueError('Confirmation must match the complete displayed prediction')
        if current is not None and current['glosses'] != list(values) and (not replace or not reason.strip()):
            raise RevisionConflict('Replacing an existing different annotation needs an explicit replacement choice and reason')
        try:
            changed = self.workspace.correct(before['example_id'], values, expected_revision=expected_revision, persist=False)
        except AnnotationRevisionConflict as exc:
            raise RevisionConflict(str(exc)) from exc
        revision = self.annotation(before['example_id'])['revision']
        if changed:
            self._metadata['revision_details'][_revision_key(before['example_id'], revision)] = {
                'prediction_id': prediction_id, 'operation_id': operation_id, 'reason': reason,
                'action': 'confirm' if confirm else 'correct'}
        receipt = {'example_id': before['example_id'], 'revision': revision, 'changed': changed,
                   'model_version': self.model_version, 'operation_id': operation_id}
        self._metadata['operations'][operation_id] = {'request': request, 'receipt': receipt}
        return copy.deepcopy(receipt)

    def save(self):
        self._validate_metadata()
        try:
            self.workspace.save()
        except ProjectWriteConflict as exc:
            raise ProjectConflict(str(exc)) from exc

    def export(self, path):
        destination = Path(path)
        if destination.exists():
            raise ValueError('Export destination already exists; choose a fresh ZIP path')
        self.save()
        return self.workspace.export(destination)


class WorkspaceStore:
    def create(self, path, *, name, language, mode='rules'):
        if Path(path).suffix != '.dproj':
            raise ValueError('Production workspace paths must end in .dproj')
        workspace = LanguageProject.create(path, name, language, {'mode': mode})
        return WorkspaceProject(workspace)

    def open(self, path):
        return WorkspaceProject(LanguageProject.open(path))
