"""Unicode corpus records with a public-input boundary and strict readers."""
from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata


def nfc(text):
    return unicodedata.normalize('NFC', text)

@dataclass(frozen=True)
class TextExample:
    id: str
    tokens: tuple[str, ...]

@dataclass(frozen=True)
class Analysis:
    lemma: str | None
    upos: str | None
    feats: tuple[str, ...] | None

    def to_dict(self):
        return {'lemma': self.lemma, 'upos': self.upos, 'feats': list(self.feats) if self.feats is not None else None}

@dataclass(frozen=True)
class AnnotatedSentence:
    example: TextExample
    analyses: tuple[Analysis, ...]


def features(value):
    if value is None:
        return None
    if isinstance(value, str):
        values = [] if value == '_' else value.split('|')
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        raise ValueError('feats must be a list, a CoNLL-U feature string, or null')
    if any(not isinstance(item, str) or not re.fullmatch(r'[^=|\s]+=[^=|\s]+', item) for item in values):
        raise ValueError('Each feature must have the form Name=Value')
    keys = [item.split('=', 1)[0] for item in values]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate morphological feature names')
    return tuple(sorted(nfc(item) for item in values))


def analysis_from_dict(value):
    if not isinstance(value, dict) or set(value) != {'lemma', 'upos', 'feats'}:
        raise ValueError('Each analysis must contain lemma, upos, and feats')
    for field in ('lemma', 'upos'):
        if value[field] is not None and (not isinstance(value[field], str) or not value[field]):
            raise ValueError(f'{field} must be a nonempty string or null')
    return Analysis(nfc(value['lemma']) if value['lemma'] is not None else None,
                    nfc(value['upos']) if value['upos'] is not None else None, features(value['feats']))


def validate(sentence):
    ex = sentence.example
    if not isinstance(ex.id, str) or not ex.id.strip() or not ex.tokens:
        raise ValueError('A sentence needs a nonempty ID and tokens')
    if len(ex.tokens) != len(sentence.analyses):
        raise ValueError('Tokens and annotations must be aligned one to one')
    if any(not isinstance(token, str) or not token.strip() or any(c in token for c in '\r\n\t') for token in ex.tokens):
        raise ValueError('Tokens must be nonempty strings without tab or line breaks')
    for analysis in sentence.analyses:
        if not isinstance(analysis, Analysis) or analysis != analysis_from_dict(analysis.to_dict()):
            raise ValueError('Annotations must be canonical Analysis records')
    return sentence


def read_conllu(path):
    path = Path(path)
    words, labels, sent_id = [], [], None
    number = 0
    with path.open(encoding='utf-8-sig') as handle:
        for line_number, raw in enumerate(handle, 1):
            line = raw.rstrip('\r\n')
            if not line:
                if words:
                    number += 1
                    yield validate(AnnotatedSentence(TextExample(sent_id or f'{path.name}:{number}', tuple(words)), tuple(labels)))
                words, labels, sent_id = [], [], None
                continue
            if line.startswith('#'):
                if line.startswith('# sent_id = '):
                    sent_id = line[len('# sent_id = '):].strip()
                continue
            columns = line.split('\t')
            if len(columns) != 10:
                raise ValueError(f'{path}:{line_number}: expected 10 tab-separated CoNLL-U fields')
            index, form, lemma, upos, _, feats, *_ = columns
            if re.fullmatch(r'[1-9]\d*-[1-9]\d*|\d+\.\d+', index):
                continue  # Evaluate supplied syntactic words, not multiword/empty rows.
            if not index.isdecimal() or int(index) != len(words)+1:
                raise ValueError(f'{path}:{line_number}: nonsequential word ID {index}')
            words.append(nfc(form))
            labels.append(Analysis(None if lemma == '_' else nfc(lemma), None if upos == '_' else nfc(upos), features(feats)))
        if words:
            number += 1
            yield validate(AnnotatedSentence(TextExample(sent_id or f'{path.name}:{number}', tuple(words)), tuple(labels)))


def read_jsonl(path):
    with Path(path).open(encoding='utf-8-sig') as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
                if not isinstance(row, dict) or not isinstance(row.get('tokens'), list) or not isinstance(row.get('analyses'), list):
                    raise ValueError('Expected id, tokens list, and analyses list')
                yield validate(AnnotatedSentence(TextExample(row['id'], tuple(nfc(t) for t in row['tokens'])), tuple(analysis_from_dict(a) for a in row['analyses'])))
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError(f'{path}:{line_number}: {exc}') from exc


def read_corpus(path):
    reader = read_conllu if Path(path).suffix == '.conllu' else read_jsonl
    seen = set()
    for sentence in reader(path):
        if sentence.example.id in seen:
            raise ValueError(f'Duplicate sentence ID: {sentence.example.id}')
        seen.add(sentence.example.id)
        yield sentence


def sentence_dict(sentence):
    return {'id': sentence.example.id, 'tokens': list(sentence.example.tokens), 'analyses': [a.to_dict() for a in sentence.analyses]}
