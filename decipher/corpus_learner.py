"""Incremental corpus morphology with lexical, contextual, and affix evidence.

No vocabulary, POS labels, grammatical features, or affix strings are supplied
by the synthetic generator. All statistics come from released annotations.
"""
from collections import Counter, defaultdict
import gzip
import json
import math
from pathlib import Path
import tempfile
from .corpus import Analysis, AnnotatedSentence, TextExample, analysis_from_dict, sentence_dict, validate, nfc

ALGORITHM_ID = 'count-affix-v1'
UNKNOWN = Analysis(None, None, None)


def best(counts):
    return min(counts, key=lambda item: (-counts[item], str(item)))


def shape(word):
    return ('upper' if word.isupper() else 'title' if word.istitle() else 'lower' if word.islower() else 'mixed',
            str(any(c.isdigit() for c in word)), str(any(not c.isalnum() for c in word)))


def lemma_rule(word, lemma):
    source, target = word.lower(), lemma.lower()
    common = 0
    while common < min(len(source), len(target)) and source[common] == target[common]:
        common += 1
    mode = 'lower' if lemma == lemma.lower() else 'title' if lemma == lemma.title() else 'copy' if lemma == word else 'literal'
    return (source[common:], target[common:], mode, lemma if mode == 'literal' else '')


def apply_rule(word, rule):
    remove, append, mode, literal = rule
    source = word.lower()
    if remove and not source.endswith(remove):
        return None
    # Whole-word replacement cannot transfer to an unrelated unknown root.
    if remove and len(remove) >= len(source):
        return None
    root = source[:-len(remove)] if remove else source
    result = root + append
    if not result:
        return None
    if mode == 'literal':
        return None
    if mode == 'title':
        return result.title()
    if mode == 'copy' and not remove and not append:
        return word
    return result


class CorpusLearner:
    def __init__(self, model='affix'):
        if model not in ('memory', 'lexicon', 'affix'):
            raise ValueError('Corpus model must be memory, lexicon, or affix')
        self.model = model
        self.records = {}
        self.version = 0
        self._reset_counts()

    def _reset_counts(self):
        self.sentence_memory = {}
        self.lexicon = defaultdict(Counter)
        self.tags = Counter()
        self.suffix = defaultdict(Counter)
        self.context = defaultdict(Counter)
        self.shapes = defaultdict(Counter)
        self.lemmas = defaultdict(Counter)
        self.rules = defaultdict(Counter)
        self.token_count = 0

    def _observe(self, sentence):
        tokens = sentence.example.tokens
        self.sentence_memory[tokens] = sentence.analyses
        for i, (word, analysis) in enumerate(zip(tokens, sentence.analyses)):
            if analysis.upos is None or analysis.feats is None or analysis.lemma is None:
                continue
            tag = (analysis.upos, analysis.feats)
            self.lexicon[word][analysis] += 1
            self.tags[tag] += 1
            self.lemmas[(word, tag)][analysis.lemma] += 1
            self.shapes[shape(word)][tag] += 1
            lower = word.lower()
            previous = tokens[i-1].lower() if i else '<BOS>'
            following = tokens[i+1].lower() if i+1 < len(tokens) else '<EOS>'
            self.context[('previous', previous)][tag] += 1
            self.context[('next', following)][tag] += 1
            rule = lemma_rule(word, analysis.lemma)
            for length in range(1, min(5, len(lower))+1):
                ending = lower[-length:]
                self.suffix[ending][tag] += 1
                self.rules[(ending, tag)][rule] += 1
                self.rules[(ending, analysis.upos)][rule] += 1
            self.token_count += 1

    def correct(self, example, analyses):
        sentence = validate(AnnotatedSentence(example, tuple(analyses)))
        previous = self.records.get(example.id)
        if previous == sentence:
            return False
        if previous is not None and previous.example != example:
            raise ValueError('A correction ID cannot refer to different source tokens')
        if previous is not None:
            del self.records[example.id]
        self.records[example.id] = sentence
        if previous is None:
            self._observe(sentence)
        else:
            # Revision replaces authoritative history, rather than double-counting.
            self._reset_counts()
            for record in self.records.values():
                self._observe(record)
        self.version += 1
        return True

    def _tag(self, tokens, index):
        word = tokens[index]
        lexicon = self.lexicon.get(word)
        if lexicon:
            base = Counter()
            for analysis, count in lexicon.items():
                base[(analysis.upos, analysis.feats)] += count
        else:
            lower = word.lower()
            base = None
            for length in range(min(5, len(lower)), 0, -1):
                counts = self.suffix.get(lower[-length:])
                if counts and sum(counts.values()) >= 3:
                    base = counts
                    break
            if base is None:
                base = self.shapes.get(shape(word)) or self.tags
        candidates = sorted(base, key=lambda t: (-base[t], t))[:24]
        total = sum(base.values())
        previous = tokens[index-1].lower() if index else '<BOS>'
        following = tokens[index+1].lower() if index+1 < len(tokens) else '<EOS>'
        contexts = [self.context.get(('previous', previous)), self.context.get(('next', following))]
        contexts = [(counts, sum(counts.values())) for counts in contexts if counts]
        shape_counts = self.shapes.get(shape(word))
        shape_total = sum(shape_counts.values()) if shape_counts else 0
        scores = {}
        for tag in candidates:
            prior = (self.tags[tag]+.1)/(self.token_count+.1*len(self.tags))
            score = math.log((base[tag]+.2*prior)/(total+.2))
            for counts, context_total in contexts:
                probability = (counts.get(tag, 0)+10*prior)/(context_total+10)
                score += .35*math.log(probability/prior)
            if not lexicon:
                counts = shape_counts
                if counts:
                    probability = (counts.get(tag, 0)+10*prior)/(shape_total+10)
                    score += .3*math.log(probability/prior)
            scores[tag] = score
        return min(scores, key=lambda tag: (-scores[tag], tag))

    def _lemma(self, word, tag):
        known = self.lemmas.get((word, tag))
        if known:
            return best(known)
        if self.lexicon.get(word):
            return best(self.lexicon[word]).lemma
        lower = word.lower()
        for length in range(min(5, len(lower)), 0, -1):
            ending = lower[-length:]
            for category in (tag, tag[0]):
                rules = self.rules.get((ending, category))
                if not rules:
                    continue
                candidates = {}
                for rule, count in rules.items():
                    prediction = apply_rule(word, rule)
                    if prediction is not None:
                        # Favor supported, short edits over one-off whole-word rules.
                        candidates[rule] = (count, -(len(rule[0])+len(rule[1])), prediction)
                if candidates:
                    rule = min(candidates, key=lambda r: (-candidates[r][0], -candidates[r][1], r))
                    return candidates[rule][2]
        return word

    def predict(self, example, model=None, verified_memory=True):
        mode = self.model if model is None else model
        if mode not in ('memory', 'lexicon', 'affix'):
            raise ValueError('Unknown corpus model')
        if not isinstance(example, TextExample):
            raise TypeError('predict accepts only TextExample, never gold annotations')
        if verified_memory and example.tokens in self.sentence_memory:
            return self.sentence_memory[example.tokens]
        if not self.tags:
            return tuple(UNKNOWN for _ in example.tokens)
        predictions = []
        for i, word in enumerate(example.tokens):
            known = self.lexicon.get(word)
            if mode in ('memory', 'lexicon'):
                if known:
                    predictions.append(best(known))
                elif mode == 'memory':
                    predictions.append(UNKNOWN)
                else:
                    tag = best(self.tags)
                    predictions.append(Analysis(word, tag[0], tag[1]))
            else:
                tag = self._tag(example.tokens, i)
                predictions.append(Analysis(self._lemma(word, tag), tag[0], tag[1]))
        return tuple(predictions)

    def save(self, path):
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        state = {'schema_version': 1, 'algorithm_id': ALGORITHM_ID, 'model': self.model, 'version': self.version,
                 'records': [sentence_dict(s) for s in self.records.values()]}
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
        try:
            with gzip.open(temporary, 'wt', encoding='utf-8') as handle:
                json.dump(state, handle, ensure_ascii=False)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    @classmethod
    def load(cls, path):
        with gzip.open(path, 'rt', encoding='utf-8') as handle:
            state = json.load(handle)
        if state.get('schema_version') != 1 or state.get('algorithm_id', ALGORITHM_ID) != ALGORITHM_ID:
            raise ValueError('Unsupported corpus checkpoint schema')
        learner = cls(state['model'])
        for row in state['records']:
            example = TextExample(row['id'], tuple(row['tokens']))
            if example.id in learner.records:
                raise ValueError('Duplicate sentence ID in checkpoint')
            learner.correct(example, tuple(analysis_from_dict(a) for a in row['analyses']))
        learner.version = state['version']
        return learner
