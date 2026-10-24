"""Teaching controller and the backend contract shared with workspace owners.

Storage is injected. This module neither chooses nor implements a project format.
"""
import copy
from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Protocol
import uuid

from .corpus import TextExample, nfc
from .gloss_checkpoint import digest, encoded


class RevisionConflict(ValueError):
    """The user reviewed an annotation that has since changed."""


class ProjectConflict(ValueError):
    """Another client saved this workspace; reload before changing it."""


def learner_identity(learner):
    """Opaque identity changes with model evidence, ordering, settings or engine."""
    return digest(encoded({'engine_sha256': digest(Path(__file__).with_name('gloss.py').read_text(encoding='utf-8').encode('utf-8')),
                           'mode': learner.mode, 'max_rules': learner.max_rules,
                           'paradigm_window': learner.paradigm_window, 'version': learner.version,
                           'records': [{'id': row.example.id, 'tokens': row.example.tokens, 'glosses': row.glosses}
                                       for row in learner.records.values()]}))


def public_example(identifier, text):
    if not isinstance(identifier, str) or not identifier.strip() or len(identifier) > 512 or any(c in identifier for c in '\r\n\t'):
        raise ValueError('Sentence ID must be a nonempty string of at most 512 characters')
    if isinstance(text, str):
        tokens = tuple(nfc(word) for word in text.split())
    elif isinstance(text, (tuple, list)):
        if any(not isinstance(word, str) for word in text):
            raise ValueError('Source words must be strings')
        tokens = tuple(nfc(word) for word in text)
    else:
        raise ValueError('Provide source text or a list of word tokens')
    if not tokens or any(not word or any(c.isspace() for c in word) for word in tokens):
        raise ValueError('Provide nonempty, separately segmented source words')
    if sum(len(word.encode('utf-8')) for word in tokens) > 1000000:
        raise ValueError('Source exceeds one million UTF-8 bytes')
    return TextExample(nfc(identifier), tokens)


def aligned_glosses(values, tokens):
    if isinstance(values, str):
        values = values.split()
    if not isinstance(values, (list, tuple)) or len(values) != len(tokens):
        raise ValueError(f'Expected {len(tokens)} aligned word glosses')
    if any(not isinstance(value, str) or not value or any(c.isspace() for c in value) for value in values):
        raise ValueError('Each word needs one nonempty gloss without whitespace')
    return tuple(nfc(value) for value in values)


def validate_predictions(predictions, tokens):
    if not isinstance(predictions, list) or len(predictions) != len(tokens):
        raise ValueError('Backend predictions must align one to one with source words')
    for word in predictions:
        if type(word.get('known_form')) is not bool or not isinstance(word.get('candidates'), list):
            raise ValueError('Predictions need known_form and full candidates')
        for candidate in word['candidates']:
            if (not isinstance(candidate.get('gloss'), str) or not candidate['gloss']
                    or not isinstance(candidate.get('score'), (int, float))
                    or not math.isfinite(candidate['score']) or not isinstance(candidate.get('kind'), str)):
                raise ValueError('Malformed candidate from project backend')
        expected = word['candidates'][0]['gloss'] if word['candidates'] else None
        if word.get('gloss') != expected:
            raise ValueError('Top gloss must match the first candidate, or be unknown')
    return copy.deepcopy(predictions)


class LanguageProject(Protocol):
    project_id: str
    name: str
    language: str

    @property
    def model_version(self) -> int: ...
    def submit(self, example: TextExample) -> bool: ...
    def examples(self) -> tuple[TextExample, ...]: ...
    def predict(self, example: TextExample) -> list[dict]: ...
    def remember_prediction(self, record: dict) -> None: ...
    def prediction(self, identifier: str) -> dict: ...
    def annotation(self, identifier: str) -> dict | None: ...
    def history(self, identifier: str) -> tuple[dict, ...]: ...
    def correct(self, prediction_id: str, glosses: tuple[str, ...], *, expected_revision: int,
                operation_id: str, reason: str, replace: bool, confirm: bool) -> dict: ...
    def model_identity(self) -> str: ...
    def training_sources(self) -> tuple[tuple[str, ...], ...]: ...
    def save(self) -> None: ...
    def export(self, path: Path) -> None: ...


class ProjectStore(Protocol):
    def create(self, path: Path, *, name: str, language: str, mode: str) -> LanguageProject: ...
    def open(self, path: Path) -> LanguageProject: ...


class TeachingService:
    def __init__(self, project: LanguageProject):
        self.project = project

    def submit(self, identifier, text):
        example = public_example(identifier, text)
        changed = self.project.submit(example)
        self.project.save()
        return {'id': example.id, 'tokens': list(example.tokens), 'added': changed}

    def example(self, identifier):
        identifier = nfc(identifier)
        for example in self.project.examples():
            if example.id == identifier:
                return example
        raise ValueError(f'Unknown sentence ID: {identifier}')

    def predict(self, identifier):
        example = self.example(identifier)
        annotation = self.project.annotation(example.id)
        record = {'prediction_id': uuid.uuid4().hex, 'example_id': example.id, 'tokens': list(example.tokens),
                  'model_version': self.project.model_version,
                  'model_identity': self.project.model_identity(),
                  'annotation_revision': annotation['revision'] if annotation else 0,
                  'timestamp': datetime.now(timezone.utc).isoformat(),
                  'words': validate_predictions(self.project.predict(example), example.tokens)}
        self.project.remember_prediction(record)
        self.project.save()
        return copy.deepcopy(record)

    def correct(self, prediction_id, glosses, *, operation_id=None, expected_revision=None,
                replace=False, reason='', confirm=False):
        before = self.project.prediction(prediction_id)
        values = aligned_glosses(glosses, before['tokens'])
        revision = before['annotation_revision'] if expected_revision is None else expected_revision
        if type(revision) is not int or revision < 0:
            raise ValueError('Expected revision must be a nonnegative integer')
        receipt = self.project.correct(prediction_id, values, expected_revision=revision,
                                       operation_id=operation_id or uuid.uuid4().hex,
                                       reason=reason, replace=replace, confirm=confirm)
        self.project.save()
        example = self.example(before['example_id'])
        return {'before': before, 'correction': receipt,
                'after': {'model_version': self.project.model_version,
                          'words': validate_predictions(self.project.predict(example), example.tokens)}}

    def confirm(self, prediction_id, *, operation_id=None):
        before = self.project.prediction(prediction_id)
        glosses = [word['gloss'] for word in before['words']]
        if any(gloss is None for gloss in glosses):
            raise ValueError('Cannot confirm unknown words; enter complete aligned glosses')
        return self.correct(prediction_id, glosses, operation_id=operation_id, confirm=True,
                            reason='Confirmed the displayed complete prediction')
