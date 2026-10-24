"""Opt-in surface-normalization backoff for unseen gloss source forms.

An unseen form such as ``table,`` or ``Table`` often differs from a taught form
only by attached punctuation or capitalization. This learner leaves every known
form unchanged; only for an unseen form does it look up taught forms sharing the
same normalized key, then retry affix rules on the normalized spelling. Glosses
still come only from teacher-grounded answers. Apostrophe-like marks are kept
because several orthographies use them as letters (for example Tsez ``ƛ’``).
Predictions keep ``known_form`` false, so review still flags them.
"""
from collections import Counter, defaultdict
import unicodedata

from .gloss import GlossLearner

APOSTROPHES = frozenset("'’ʼʻ`")


def _edge_punctuation(char):
    return char not in APOSTROPHES and unicodedata.category(char).startswith('P')


def strip_edges(word):
    start, end = 0, len(word)
    while start < end and _edge_punctuation(word[start]):
        start += 1
    while end > start and _edge_punctuation(word[end-1]):
        end -= 1
    return word[start:end]


def surface_key(word):
    return strip_edges(word).casefold()


class BackoffGlossLearner(GlossLearner):
    def _reset(self):
        super()._reset()
        self.surface_lexicon = defaultdict(Counter)

    def _observe(self, record):
        super()._observe(record)
        for word, gloss in zip(record.example.tokens, record.glosses):
            key = surface_key(word)
            if key:
                self.surface_lexicon[key][gloss] += 1

    def word_candidates(self, word):
        if word in self.lexicon or self.mode == 'memory':
            return super().word_candidates(word)
        key = surface_key(word)
        counts = self.surface_lexicon.get(key) if key else None
        if counts:
            total = sum(counts.values())
            return [{'gloss': g, 'score': counts[g]/total, 'kind': 'normalized_lexical', 'anchor': key}
                    for g in sorted(counts, key=lambda g: (-counts[g], g))[:5]]
        candidates = super().word_candidates(word)
        if candidates:
            return candidates
        for variant in dict.fromkeys((strip_edges(word), key)):
            if variant and variant != word:
                candidates = super().word_candidates(variant)
                if candidates:
                    return [{**row, 'normalized_from': word} for row in candidates]
        return []
