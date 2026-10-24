"""Portable, revisioned workspaces for source-only gloss teaching."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import zipfile

from .corpus import TextExample, nfc
from .gloss import GlossExample, GlossLearner, load_gloss


SCHEMA_VERSION = 1
DEFAULT_MODEL_CONFIG = {
    'mode': 'rules',
    'max_rules': 512,
    'paradigm_window': 32,
    'contextual': True,
}
MAX_IMPORT_BYTES = 25 * 1024 * 1024


class ProjectWriteConflict(ValueError):
    """A saved workspace changed after this client opened it."""


class AnnotationRevisionConflict(ValueError):
    """The supplied reviewed annotation revision is no longer current."""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _validate_name(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 120:
        raise ValueError(f'{field} must be a nonempty string of at most 120 characters')
    return value.strip()


def _model_config(value):
    if not isinstance(value, dict) or set(value)-set(DEFAULT_MODEL_CONFIG):
        raise ValueError('Model configuration contains unsupported fields')
    config = {**DEFAULT_MODEL_CONFIG, **value}
    GlossLearner(**config)
    return config


def _records_from_text(content, name, format):
    if not isinstance(content, str) or not content.strip():
        raise ValueError('Imported corpus must contain text')
    if format == 'sigmorphon':
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'corpus.txt'
            path.write_text(content, encoding='utf-8')
            records, _ = load_gloss(path, require_gold=False)
        return records
    records = []
    for line_number, line in enumerate(content.splitlines(), 1):
        if not line.strip():
            continue
        if format == 'text':
            source, labels = line.strip(), None
        elif format == 'tsv':
            columns = line.split('\t')
            if len(columns) not in (1, 2):
                raise ValueError(f'{name}:{line_number}: expected source words and optional tab-separated glosses')
            source = columns[0].strip()
            labels = tuple(nfc(value) for value in columns[1].split()) if len(columns) == 2 else None
        else:
            raise ValueError('Corpus format must be text, tsv, or sigmorphon')
        tokens = tuple(nfc(token) for token in source.split())
        if not tokens:
            raise ValueError(f'{name}:{line_number}: source sentence is empty')
        if labels is not None and (not labels or len(labels) != len(tokens)):
            raise ValueError(f'{name}:{line_number}: source and gloss words must be aligned')
        records.append(GlossExample(TextExample(f'{name}:{line_number}', tokens), labels))
    if not records:
        raise ValueError('Imported corpus has no sentences')
    return records


class LanguageProject:
    """A single language workspace whose model is rebuilt from annotation history."""

    def __init__(self, path, data):
        self.path = Path(path)
        self._disk_digest = None
        self.data = data
        self._validate()
        config = _model_config(data['model_config'])
        self.model = GlossLearner(**config)
        self.model.fit(self._latest_annotations().values())
        self.model.version = data['checkpoint']['model_version']

    @classmethod
    def create(cls, path, name, language_id, model_config=None):
        destination = Path(path)
        if destination.suffix != '.dproj':
            destination = destination.with_suffix('.dproj')
        if destination.exists():
            raise FileExistsError(f'Project already exists: {destination}')
        config = _model_config(DEFAULT_MODEL_CONFIG if model_config is None else model_config)
        data = {
            'schema_version': SCHEMA_VERSION,
            'project_id': destination.stem,
            'name': _validate_name(name, 'Project name'),
            'language_id': _validate_name(language_id, 'Language ID'),
            'model_config': config,
            'corpora': [],
            'sentences': [],
            'annotation_history': [],
            'checkpoint': {'model_version': 0, 'annotation_count': 0},
        }
        project = cls(destination, data)
        project.save()
        return project

    @classmethod
    def open(cls, path):
        source = Path(path)
        raw = source.read_bytes()
        project = cls(source, json.loads(raw))
        project._disk_digest = hashlib.sha256(raw).hexdigest()
        return project

    @classmethod
    def restore(cls, archive, destination):
        with zipfile.ZipFile(archive) as bundle:
            members = bundle.infolist()
            if len(members) != 1 or Path(members[0].filename).name != members[0].filename:
                raise ValueError('Project backup must contain exactly one project file')
            member = members[0]
            if not member.filename.endswith('.dproj') or member.file_size > MAX_IMPORT_BYTES:
                raise ValueError('Project backup contains an unsupported or oversized file')
            raw = bundle.read(member)
        target = Path(destination)
        if target.suffix != '.dproj':
            target = target.with_suffix('.dproj')
        if target.exists():
            raise FileExistsError(f'Project already exists: {target}')
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(raw)
        try:
            restored = cls.open(temporary)
            restored.path = target
            restored._disk_digest = None
            restored.save()
            return restored
        finally:
            temporary.unlink(missing_ok=True)

    def _validate(self):
        data = self.data
        if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != SCHEMA_VERSION:
            raise ValueError('Unsupported language project schema')
        _validate_name(data.get('project_id'), 'Project ID')
        if any(character in data['project_id'] for character in ('/', '\\', '\0')):
            raise ValueError('Project ID cannot contain path separators')
        _validate_name(data.get('name'), 'Project name')
        _validate_name(data.get('language_id'), 'Language ID')
        _model_config(data.get('model_config'))
        if not isinstance(data.get('corpora'), list) or not isinstance(data.get('sentences'), list):
            raise ValueError('Project corpora and sentences must be arrays')
        for corpus in data['corpora']:
            if (not isinstance(corpus, dict) or set(corpus) != {'name', 'sha256', 'sentence_count'}
                    or not isinstance(corpus['name'], str) or not corpus['name']
                    or not isinstance(corpus['sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', corpus['sha256'])
                    or type(corpus['sentence_count']) is not int or corpus['sentence_count'] < 0):
                raise ValueError('Malformed corpus identity')
        sentence_ids = set()
        for sentence in data['sentences']:
            if (not isinstance(sentence, dict) or not isinstance(sentence.get('id'), str)
                    or not sentence['id'] or not isinstance(sentence.get('tokens'), list)
                    or not sentence['tokens'] or any(not isinstance(token, str) or not token or any(c.isspace() for c in token)
                                                      for token in sentence['tokens'])):
                raise ValueError('Malformed project sentence')
            if sentence['id'] in sentence_ids:
                raise ValueError('Duplicate project sentence ID')
            sentence_ids.add(sentence['id'])
        if not isinstance(data.get('annotation_history'), list):
            raise ValueError('Project annotation history must be an array')
        revisions = {}
        previous_glosses = {}
        corpus_by_id = {sentence['id']: tuple(sentence['tokens']) for sentence in data['sentences']}
        for item in data['annotation_history']:
            if not isinstance(item, dict) or set(item) != {'id', 'revision', 'glosses', 'timestamp'}:
                raise ValueError('Malformed project annotation revision')
            identifier = item['id']
            if not isinstance(identifier, str):
                raise ValueError('Annotation IDs must be strings')
            tokens = corpus_by_id.get(identifier)
            glosses = item['glosses']
            expected_revision = revisions.get(identifier, 0) + 1
            if (tokens is None or type(item['revision']) is not int or item['revision'] != expected_revision
                    or not isinstance(glosses, list) or len(glosses) != len(tokens)
                    or any(not isinstance(gloss, str) or not gloss or any(c.isspace() for c in gloss) for gloss in glosses)
                    or not isinstance(item['timestamp'], str)):
                raise ValueError('Invalid annotation revision or source/gloss alignment')
            if previous_glosses.get(identifier) == tuple(glosses):
                raise ValueError('Annotation history cannot contain an unchanged revision')
            revisions[identifier] = expected_revision
            previous_glosses[identifier] = tuple(glosses)
        checkpoint = data.get('checkpoint')
        if (not isinstance(checkpoint, dict)
                or type(checkpoint.get('model_version')) is not int
                or type(checkpoint.get('annotation_count')) is not int
                or checkpoint['model_version'] != len(data['annotation_history'])
                or checkpoint['annotation_count'] != len(revisions)):
            raise ValueError('Project checkpoint does not match authoritative annotations')

    def _latest_annotations(self):
        latest = {}
        corpus = {sentence['id']: sentence for sentence in self.data['sentences']}
        for item in self.data['annotation_history']:
            sentence = corpus[item['id']]
            latest.pop(item['id'], None)
            latest[item['id']] = GlossExample(TextExample(item['id'], tuple(sentence['tokens'])), tuple(item['glosses']))
        return latest

    def sentence(self, identifier):
        for item in self.data['sentences']:
            if item['id'] == identifier:
                return item
        raise ValueError(f'Unknown sentence ID: {identifier}')

    def submit(self, example, *, persist=True):
        """Register manual public source words without exposing annotations."""
        if (not isinstance(example, TextExample) or not isinstance(example.id, str) or not example.id
                or not isinstance(example.tokens, tuple) or not example.tokens
                or any(not isinstance(word, str) or not word or any(c.isspace() for c in word) for word in example.tokens)
                or type(persist) is not bool):
            raise ValueError('Submit a public sentence ID and separately segmented source words')
        identifier = nfc(example.id)
        tokens = [nfc(word) for word in example.tokens]
        for row in self.data['sentences']:
            if row['id'] == identifier:
                if row['tokens'] != tokens:
                    raise ValueError('An existing sentence ID cannot change source words')
                return False
        self.data['sentences'].append({'id': identifier, 'tokens': tokens})
        if persist:
            self.save()
        return True

    def add_corpus(self, name, content, format='auto'):
        name = _validate_name(name, 'Corpus name')
        if not isinstance(content, str):
            raise ValueError('Imported corpus content must be UTF-8 text')
        if len(content.encode('utf-8')) > MAX_IMPORT_BYTES:
            raise ValueError(f'Corpus import exceeds {MAX_IMPORT_BYTES} bytes')
        if format == 'auto':
            suffix = Path(name).suffix.lower()
            format = 'text' if suffix == '.txt' else 'tsv' if suffix == '.tsv' else 'sigmorphon'
        parsed = _records_from_text(content, name, format)
        digest = hashlib.sha256(content.encode('utf-8')).hexdigest()
        if any(corpus['sha256'] == digest for corpus in self.data['corpora']):
            return 0
        existing = {sentence['id'] for sentence in self.data['sentences']}
        additions = []
        for record in parsed:
            identifier = f'{digest[:12]}:{record.example.id}'
            if identifier in existing:
                raise ValueError('Corpus import would duplicate a sentence ID')
            existing.add(identifier)
            additions.append((identifier, record))
        for identifier, record in additions:
            self.data['sentences'].append({'id': identifier, 'tokens': list(record.example.tokens)})
            if record.glosses is not None:
                self.model.correct(TextExample(identifier, record.example.tokens), record.glosses)
                self.data['annotation_history'].append({
                    'id': identifier,
                    'revision': 1,
                    'glosses': list(record.glosses),
                    'timestamp': _now(),
                })
        self.data['corpora'].append({'name': name, 'sha256': digest, 'sentence_count': len(additions)})
        self.data['checkpoint'] = {
            'model_version': self.model.version,
            'annotation_count': len(self._latest_annotations()),
        }
        self.save()
        return len(additions)

    def correct(self, identifier, glosses, *, expected_revision=None, persist=True):
        sentence = self.sentence(identifier)
        revision = sum(item['id'] == identifier for item in self.data['annotation_history'])
        if type(persist) is not bool:
            raise ValueError('Persistence choice must be boolean')
        if expected_revision is not None:
            if type(expected_revision) is not int or expected_revision < 0:
                raise ValueError('Expected annotation revision must be a nonnegative integer')
            if expected_revision != revision:
                raise AnnotationRevisionConflict(f'Annotation changed: reviewed revision {expected_revision}, current revision {revision}. Refresh and review it again.')
        example = TextExample(identifier, tuple(sentence['tokens']))
        if not isinstance(glosses, (list, tuple)):
            raise ValueError('Glosses must be an array aligned to source words')
        labels = tuple(glosses)
        previous = self._latest_annotations().get(identifier)
        if previous is not None and previous.glosses == labels:
            return False
        if not self.model.correct(example, labels):
            return False
        revision += 1
        self.data['annotation_history'].append({
            'id': identifier,
            'revision': revision,
            'glosses': list(labels),
            'timestamp': _now(),
        })
        self.data['checkpoint'] = {
            'model_version': self.model.version,
            'annotation_count': len(self._latest_annotations()),
        }
        if persist:
            self.save()
        return True

    def predict(self, identifier):
        sentence = self.sentence(identifier)
        return self.model.predict(TextExample(identifier, tuple(sentence['tokens'])))

    @property
    def annotation_count(self):
        return len(self._latest_annotations())

    def save(self):
        self.data['checkpoint'] = {
            'model_version': self.model.version,
            'annotation_count': len(self._latest_annotations()),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_name(self.path.name+'.lock')
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ProjectWriteConflict('Project is being saved by another process. Retry after it finishes; a crashed writer lock needs explicit recovery.') from exc
        temporary = None
        try:
            actual = hashlib.sha256(self.path.read_bytes()).hexdigest() if self.path.exists() else None
            if actual != self._disk_digest:
                raise ProjectWriteConflict('Project changed on disk. Reopen it before saving; another client has newer work.')
            self._validate()
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent, delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(self.data, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            for attempt in range(6):
                try:
                    temporary.replace(self.path)
                    break
                except PermissionError:
                    if attempt == 5:
                        raise
                    time.sleep(.05 * 2**attempt)
            self._disk_digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            os.close(descriptor)
            lock.unlink(missing_ok=True)

    def export(self, destination):
        self.save()
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
        try:
            with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
                bundle.write(self.path, self.path.name)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    def queue(self):
        latest = self._latest_annotations()
        return [
            {
                'id': sentence['id'],
                'tokens': sentence['tokens'],
                'predictions': self.predict(sentence['id']),
                'annotated': sentence['id'] in latest,
                'revision': sum(item['id'] == sentence['id'] for item in self.data['annotation_history']),
            }
            for sentence in self.data['sentences']
        ]


def project_path(workspace, name):
    name = _validate_name(name, 'Project name')
    slug = re.sub(r'[^a-zA-Z0-9_-]+', '-', name).strip('-_').lower()
    if not slug:
        raise ValueError('Project name must contain a letter or number')
    return Path(workspace) / f'{slug}.dproj'


def list_projects(workspace):
    directory = Path(workspace)
    if not directory.exists():
        return []
    projects = []
    for path in sorted(directory.glob('*.dproj')):
        project = LanguageProject.open(path)
        projects.append({
            'project_id': project.data['project_id'],
            'name': project.data['name'],
            'language_id': project.data['language_id'],
        })
    return projects
