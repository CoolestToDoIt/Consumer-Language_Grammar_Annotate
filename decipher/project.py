"""Portable, revisioned workspaces for source-only gloss teaching."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import unicodedata
import zipfile

from .corpus import TextExample, nfc
from .gloss import GlossExample, GlossLearner, lexical_key, load_gloss, transform


SCHEMA_VERSION = 1
DEFAULT_MODEL_CONFIG = {
    'mode': 'rules',
    'max_rules': 512,
    'paradigm_window': 32,
    'contextual': True,
    'guess_unknown': True,
}
MAX_IMPORT_BYTES = 25 * 1024 * 1024
UNDETERMINED_LANGUAGE = 'und'  # ISO 639 code for an unidentified language
MAX_DESCRIPTION = 4000
# Data-ownership notes recorded per language; they travel with backups.
GOVERNANCE_FIELDS = ('owner', 'license', 'consent', 'provenance', 'retention', 'conventions')
MAX_KEPT_GLOSSES = 10000


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
        if not records:
            raise ValueError('Imported corpus has no source sentences; check the source tiers and selected format')
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
        description = data.get('description', '')
        if not isinstance(description, str) or len(description) > MAX_DESCRIPTION:
            raise ValueError(f'Language description must be text of at most {MAX_DESCRIPTION} characters')
        _model_config(data.get('model_config'))
        governance = data.get('governance', {})
        if (not isinstance(governance, dict) or set(governance) - set(GOVERNANCE_FIELDS)
                or any(not isinstance(v, str) or len(v) > 4000 for v in governance.values())):
            raise ValueError('Invalid project governance metadata')
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
        kept = data.get('kept_glosses', [])
        if (not isinstance(kept, list) or len(kept) > MAX_KEPT_GLOSSES
                or any(not isinstance(entry, list) or len(entry) != 3 or not isinstance(entry[0], str) or entry[0] not in sentence_ids
                       or type(entry[1]) is not int or entry[1] < 0 or not isinstance(entry[2], str) or not entry[2]
                       for entry in kept)):
            raise ValueError('Invalid list of kept glosses')
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
            format = 'sigmorphon' if any(line.startswith('\\t ') or line.startswith('\\t\t') for line in content.splitlines()) else 'tsv' if suffix == '.tsv' or '\t' in content else 'text'
        content = content.removeprefix('\ufeff')
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

    def preview_corpus(self, name, content, format='auto'):
        name = _validate_name(name, 'Corpus name')
        if not isinstance(content, str):
            raise ValueError('Imported corpus content must be UTF-8 text')
        if len(content.encode('utf-8')) > MAX_IMPORT_BYTES:
            raise ValueError(f'Corpus import exceeds {MAX_IMPORT_BYTES} bytes')
        if format == 'auto':
            suffix = Path(name).suffix.lower()
            format = 'sigmorphon' if any(line.startswith('\\t ') or line.startswith('\\t\t') for line in content.splitlines()) else 'tsv' if suffix == '.tsv' or '\t' in content else 'text'
        content = content.removeprefix('\ufeff')
        parsed = _records_from_text(content, name, format)
        digest = hashlib.sha256(content.encode('utf-8')).hexdigest()
        return {
            'name': name,
            'format': format,
            'sha256': digest,
            'duplicate': any(corpus['sha256'] == digest for corpus in self.data['corpora']),
            'sentence_count': len(parsed),
            'annotated_count': sum(record.glosses is not None for record in parsed),
            'needs_review_count': sum(record.glosses is None for record in parsed),
            'examples': [
                {'tokens': list(record.example.tokens),
                 'glosses': list(record.glosses) if record.glosses is not None else None}
                for record in parsed[:5]
            ],
        }

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

    def update_language(self, *, name=None, language_id=None, description=None):
        """Change display details only; the project file name and ID stay stable."""
        if name is not None:
            self.data['name'] = _validate_name(name, 'Language name')
        if language_id is not None:
            self.data['language_id'] = _validate_name(language_id or UNDETERMINED_LANGUAGE, 'Language ID')
        if description is not None:
            if not isinstance(description, str) or len(description) > MAX_DESCRIPTION:
                raise ValueError(f'Language description must be text of at most {MAX_DESCRIPTION} characters')
            self.data['description'] = description.strip()
        self.save()

    def summary(self):
        governance = self.data.get('governance', {})
        return {'project_id': self.data['project_id'], 'name': self.data['name'],
                'language_id': self.data['language_id'], 'description': self.data.get('description', ''),
                'sentences': len(self.data['sentences']), 'reviewed': self.annotation_count,
                'words_known': len(self.model.lexicon),
                # Which data-ownership notes are filled in (names only, not their text).
                'policy_recorded': [field for field in GOVERNANCE_FIELDS if governance.get(field, '').strip()]}

    def performance(self, *, points=12):
        """Replay saved glosses in order and score the suggestion made before each.

        Every first annotation of a sentence (imported or reviewed) is scored
        against what a fresh model, taught only the earlier annotations, would
        have suggested. Later revisions are applied but not scored. Rates are
        empirical counts on this project's own data, not calibrated confidence.
        """
        learner = GlossLearner(**_model_config(self.data['model_config']))
        tokens = {sentence['id']: tuple(sentence['tokens']) for sentence in self.data['sentences']}
        totals = dict.fromkeys(('sentences', 'words', 'accepted', 'picked', 'repeat_words', 'repeat_accepted'), 0)
        kinds = {kind: {'words': 0, 'right': 0} for kind in ('known', 'pattern', 'guess', 'none')}
        taught, per_sentence = set(), []
        last, revised, fixed = {}, set(), 0
        for entry in self.data['annotation_history']:
            example, glosses = TextExample(entry['id'], tokens[entry['id']]), tuple(entry['glosses'])
            if entry['revision'] > 1:
                # A later save that changes glosses: earlier work corrected on a second look.
                revised.add(entry['id'])
                fixed += sum(old != new for old, new in zip(last[entry['id']], glosses))
            last[entry['id']] = glosses
            if entry['revision'] == 1:
                right = 0
                for word, gold, prediction in zip(example.tokens, glosses, learner.predict(example)):
                    top = prediction['candidates'][0] if prediction['candidates'] else None
                    kind = ('none' if prediction['gloss'] is None or top is None else
                            'known' if top['kind'] in ('lexical', 'contextual') else
                            'pattern' if top['kind'] == 'rule' else 'guess')
                    accepted = prediction['gloss'] == gold
                    totals['words'] += 1
                    totals['accepted'] += accepted
                    totals['picked'] += not accepted and any(row['gloss'] == gold for row in prediction['candidates'][:5])
                    kinds[kind]['words'] += 1
                    kinds[kind]['right'] += accepted
                    if (word, gold) in taught:
                        totals['repeat_words'] += 1
                        totals['repeat_accepted'] += accepted
                    right += accepted
                totals['sentences'] += 1
                per_sentence.append((len(glosses), right))
            learner.correct(example, glosses)
            taught.update(zip(example.tokens, glosses))
        curve, size = [], max(1, -(-len(per_sentence) // points))
        for start in range(0, len(per_sentence), size):
            chunk = per_sentence[start:start+size]
            curve.append({'sentences': start + len(chunk), 'accepted': sum(r for _, r in chunk) / sum(n for n, _ in chunk)})

        def ratio(a, b):
            return a / b if b else None
        return {'sentences': totals['sentences'], 'words': totals['words'],
                'accepted': ratio(totals['accepted'], totals['words']),
                'picked': ratio(totals['picked'], totals['words']),
                'no_typing': ratio(totals['accepted'] + totals['picked'], totals['words']),
                'teach_once': ratio(totals['repeat_accepted'], totals['repeat_words']),
                'counts': totals, 'by_kind': kinds, 'curve': curve,
                'revisions': {'sentences': len(revised), 'glosses': fixed}}

    def unusual_glosses(self, *, limit=None):
        """Saved glosses that differ from how the same word is usually glossed.

        A word form that is otherwise consistent (one gloss in at least three
        quarters of its uses, and at least three times) but saved once or twice,
        and in at most a fifth of its uses, with another gloss is flagged. That is often a slip, a missing tag or a
        typo, and sometimes real ambiguity, so a person decides; glosses they
        keep are not flagged again. Words already split between common glosses
        are not flagged.
        """
        kept = {tuple(entry) for entry in self.data.get('kept_glosses', [])}
        uses = defaultdict(list)
        for annotation in self._latest_annotations().values():
            for index, (token, gloss) in enumerate(zip(annotation.example.tokens, annotation.glosses)):
                uses[token.casefold()].append((annotation.example.id, index, token, gloss))
        flagged, kept_count = [], 0
        for rows in uses.values():
            counts = Counter(row[3] for row in rows)
            usual, usual_count = counts.most_common(1)[0]
            if len(counts) < 2 or usual_count < 3 or usual_count * 4 < len(rows) * 3:
                continue
            for identifier, index, token, gloss in rows:
                if gloss == usual or counts[gloss] > 2 or counts[gloss] * 5 > len(rows):
                    continue
                if (identifier, index, gloss) in kept:
                    kept_count += 1
                else:
                    flagged.append({'id': identifier, 'index': index, 'token': token, 'gloss': gloss,
                                    'usual': usual, 'usual_count': usual_count, 'uses': len(rows)})
        flagged.sort(key=lambda row: (-row['usual_count'], row['id'], row['index']))
        return {'count': len(flagged), 'kept': kept_count, 'items': flagged if limit is None else flagged[:limit]}

    def keep_gloss(self, identifier, index, gloss):
        """Record that a person checked an unusual saved gloss and it is right."""
        latest = self._latest_annotations().get(identifier)
        if (latest is None or type(index) is not int or not 0 <= index < len(latest.glosses)
                or latest.glosses[index] != gloss):
            raise ValueError('That gloss is no longer saved. Refresh and check again.')
        kept = self.data.setdefault('kept_glosses', [])
        if [identifier, index, gloss] not in kept:
            if len(kept) >= MAX_KEPT_GLOSSES:
                raise ValueError('Too many kept glosses in one language')
            kept.append([identifier, index, gloss])
            self.save()

    def knowledge(self, *, max_endings=60, examples_per_ending=3):
        """Read-only view of what the model has learned from reviewed glosses.

        Vocabulary groups taught word forms by lexical meaning (the lowercase
        parts of a Leipzig-style gloss). Endings are the model's own affix rules
        that add a purely grammatical tag, with the number of distinct meanings
        supporting each one and taught example pairs. Counts are evidence, not
        probabilities.
        """
        model = self.model
        vocabulary = []
        for key, pairs in model.paradigms.items():
            forms = [{'form': word, 'gloss': gloss, 'count': model.lexicon[word][gloss]} for word, gloss in pairs]
            forms.sort(key=lambda row: (len(row['form']), row['form']))
            vocabulary.append({'meaning': '-'.join(key), 'forms': forms,
                               'count': sum(row['count'] for row in forms)})
        vocabulary.sort(key=lambda row: (-row['count'], row['meaning']))
        function_words = sorted(
            ({'form': word, 'gloss': gloss, 'count': count}
             for word, counts in model.lexicon.items() for gloss, count in counts.items() if not lexical_key(gloss)),
            key=lambda row: (-row['count'], row['form']))
        def grammatical(tag):
            return bool(tag) and any(c.isupper() for c in tag) and not any(c.islower() for c in tag)

        def aligned(gloss, side, edit):
            # The gloss edit must start at a tag boundary of a real taught gloss,
            # so "see-PRS -> see-PST" is PRS -> PST, never "RS -> ST".
            if edit and (edit[0] if side == 'suffix' else edit[-1]) in '-=':
                return True
            kept = gloss[:len(gloss)-len(edit)] if side == 'suffix' else gloss[len(edit):]
            return (kept[-1:] if side == 'suffix' else kept[:1]) in ('-', '=')

        def letters(affix):
            # Attached punctuation ("in." / "no,") is not an ending; apostrophes
            # stay because some orthographies write ejectives with them.
            return all(c in "'’ʼ" or not unicodedata.category(c).startswith('P') for c in affix)

        def examples(rule):
            side, remove, append, target_side, remove_gloss, append_gloss = rule
            found = []
            for word, counts in model.lexicon.items():
                derived = transform(word, side, remove, append)
                if derived is None or derived not in model.lexicon:
                    continue
                for gloss in counts:
                    target = transform(gloss, target_side, remove_gloss, append_gloss)
                    if (target in model.lexicon[derived] and lexical_key(gloss)
                            and (aligned(gloss, target_side, remove_gloss) or aligned(target, target_side, append_gloss))):
                        found.append({'base': word, 'base_gloss': gloss, 'form': derived, 'gloss': target})
                        break
                if len(found) >= examples_per_ending:
                    break
            return found

        # A rule maps a base form to a derived form by removing one affix and
        # appending another. "add" rules attach a grammatical tag to a bare
        # form; "swap" rules exchange one tag for another (e.g. PRS -> PST).
        candidates = []
        for rule in model._rules():
            side, remove, append, target_side, remove_gloss, append_gloss = rule
            tag, old_tag = append_gloss.strip('-='), remove_gloss.strip('-=')
            if (not append or not grammatical(tag) or len(model.rule_evidence[rule]) < 2
                    or not letters(append) or not letters(remove)):
                continue
            if remove or remove_gloss:
                if not remove or not grammatical(old_tag):
                    continue
                candidates.append(('swap', rule, tag, old_tag))
            else:
                candidates.append(('add', rule, tag, ''))
        added = {tag for kind, _, tag, _ in candidates if kind == 'add'}
        endings, seen = [], set()
        for kind, rule, tag, old_tag in candidates:
            if len(endings) >= max_endings:
                break
            side, remove, append = rule[:3]
            if kind == 'swap':
                # Each swap is also learned in reverse; skip swaps already
                # explained by "add" endings and stacked affixes like -ek -> -umek.
                if ({tag, old_tag} <= added or (side == 'suffix' and (append.endswith(remove) or remove.endswith(append)))
                        or (side == 'prefix' and (append.startswith(remove) or remove.startswith(append)))):
                    continue
                identity = (side, frozenset({(remove, old_tag), (append, tag)}))
            else:
                identity = (side, append, tag)
            if identity in seen:
                continue
            found = examples(rule)
            if not found:
                continue
            seen.add(identity)
            endings.append({'kind': kind, 'side': side, 'affix': append, 'tag': tag,
                            'replaces_affix': remove, 'replaces_tag': old_tag,
                            'meanings': len(model.rule_evidence[rule]), 'examples': found})
        endings.sort(key=lambda row: (row['kind'] != 'add', -row['meanings'], len(row['affix']), row['affix'], row['tag']))
        return {'vocabulary': vocabulary, 'function_words': function_words, 'endings': endings,
                'stats': {'word_forms': len(model.lexicon), 'meanings': len(vocabulary),
                          'endings': len(endings), 'reviewed': self.annotation_count,
                          'sentences': len(self.data['sentences'])}}

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
                if handle.tell() > MAX_IMPORT_BYTES:
                    raise ValueError('Project exceeds the 25 MiB portable workspace limit. Split the corpus into smaller projects.')
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
        entries = []
        for position, sentence in enumerate(self.data['sentences']):
            predictions = self.predict(sentence['id'])
            entries.append({
                'id': sentence['id'],
                'tokens': sentence['tokens'],
                'predictions': predictions,
                'annotated': sentence['id'] in latest,
                'glosses': list(latest[sentence['id']].glosses) if sentence['id'] in latest else None,
                'revision': sum(item['id'] == sentence['id'] for item in self.data['annotation_history']),
                'tentative_words': sum(bool(item.get('provisional')) for item in predictions),
                'needs_gloss_words': sum(item['gloss'] is None for item in predictions),
                'position': position,
            })
        entries.sort(key=lambda item:(item['annotated'], -item['needs_gloss_words'],
                                      -item['tentative_words'], item['position']))
        for entry in entries:
            entry.pop('position')
        return entries


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
        projects.append(LanguageProject.open(path).summary())
    return projects
