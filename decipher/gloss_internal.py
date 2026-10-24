"""Experimental prepared internal-edit overlay; never used by default commands.

The authoritative GlossLearner remains unchanged. Internal and edge rules share
its one total rule budget and voting formula. Surface codepoint edits are not
gold morpheme segmentations or discoveries of ungrounded meanings.
"""
from collections import Counter, defaultdict
import heapq

from .corpus import TextExample
from .gloss import GlossLearner, common_prefix, edit, lexical_key, transform

ALGORITHM_ID = 'grounded-internal-stem-overlay-v1'


def internal_edit(first, second):
    """Canonical middle block, keeping nonoverlapping unchanged sides.

    Keep the longest common prefix that leaves a suffix character, then the
    longest remaining common suffix, including repeated-character deletions.
    """
    if first == second or min(len(first), len(second)) < 2:
        return None
    prefix = min(common_prefix(first, second), min(len(first), len(second))-1)
    if prefix < 1:
        return None
    suffix = common_prefix(first[prefix:][::-1], second[prefix:][::-1])
    if suffix < 1:
        return None
    remove = first[prefix:len(first)-suffix]
    append = second[prefix:len(second)-suffix]
    return (remove, append) if remove != append else None


class StaleOverlayError(ValueError):
    pass


class InternalGlossOverlay:
    """Explicitly prepared, nonmutating inference over a frozen rules learner."""
    def __init__(self, base):
        if not isinstance(base, GlossLearner):
            raise TypeError('The overlay needs an authoritative GlossLearner')
        self.base = base
        self._prepared_signature = None
        self.prepare()

    def _signature(self):
        base = self.base
        return base.version, base.mode, base.max_rules, base.paradigm_window, base.contextual

    def _check(self):
        if self._signature() != self._prepared_signature:
            raise StaleOverlayError('Underlying learner changed; explicitly prepare the internal overlay again')

    def prepare(self):
        base = self.base
        if base.mode != 'rules' or base.contextual:
            raise ValueError('The isolated overlay requires rules mode with contextual=False')
        if base._rule_cache is None:
            raise ValueError('Finish base fitting/correction before preparing an overlay')
        signature = self._signature()
        internal = defaultdict(set)
        for key, paradigm in base.paradigms.items():
            for index, (word, gloss) in enumerate(paradigm):
                for other, other_gloss in paradigm[max(0, index-base.paradigm_window):index]:
                    if word == other or gloss == other_gloss:
                        continue
                    pieces = internal_edit(other, word)
                    if pieces is None:
                        continue
                    remove, append = pieces
                    for side in ('prefix', 'suffix'):
                        remove_gloss, append_gloss, shared = edit(other_gloss, gloss, side)
                        if shared < 2 or not (remove_gloss or append_gloss):
                            continue
                        internal[('internal', remove, append, side, remove_gloss, append_gloss)].add(key)
                        internal[('internal', append, remove, side, append_gloss, remove_gloss)].add(key)
        evidence = {rule: frozenset(keys) for rule, keys in base.rule_evidence.items()}
        evidence.update((rule, frozenset(keys)) for rule, keys in internal.items())
        def rank(rule):
            return (-len(evidence[rule]), sum(len(value) for value in (rule[1], rule[2], rule[4], rule[5])), rule)
        rules = tuple(heapq.nsmallest(base.max_rules, evidence, key=rank))
        edge_index, internal_index = defaultdict(list), defaultdict(list)
        for position, rule in enumerate(rules):
            if rule[0] == 'internal':
                internal_index[rule[2]].append((position, rule))
            else:
                edge_index[(rule[0], rule[2])].append((position, rule))
        lengths = {side: tuple(sorted({len(affix) for kind, affix in edge_index if kind == side}))
                   for side in ('prefix', 'suffix')}
        if signature != self._signature():
            raise StaleOverlayError('Underlying learner changed during preparation')
        self._evidence = evidence
        self._internal_evidence = {rule: frozenset(keys) for rule, keys in internal.items()}
        self._rules = rules
        self._edge_index = dict(edge_index)
        self._edge_lengths = lengths
        self._internal_index = dict(internal_index)
        self._internal_lengths = tuple(sorted({len(append) for append in internal_index}))
        self._prepared_signature = signature
        return self

    @property
    def selected_rules(self):
        self._check()
        return self._rules

    def _recoveries(self, word):
        """Ordered recoveries; duplicate edit positions vote once per anchor/rule."""
        matches = defaultdict(set)
        for side, lengths in self._edge_lengths.items():
            for length in lengths:
                if length > len(word):
                    break
                affix = word[:length] if side == 'prefix' else word[len(word)-length:]
                for position, rule in self._edge_index.get((side, affix), ()):
                    anchor = transform(word, side, rule[2], rule[1])
                    if anchor and anchor != word and anchor in self.base.lexicon:
                        matches[position].add(anchor)
        for length in self._internal_lengths:
            if length > len(word)-2:
                break
            for start in range(1, len(word)-length):
                end = start+length
                for position, rule in self._internal_index.get(word[start:end], ()):
                    anchor = word[:start]+rule[1]+word[end:]
                    if anchor != word and anchor in self.base.lexicon:
                        matches[position].add(anchor)
        return [(self._rules[position], tuple(sorted(anchors))) for position, anchors in sorted(matches.items())]

    def recoveries(self, word):
        self._check()
        if not isinstance(word, str) or not word or any(c.isspace() for c in word):
            raise ValueError('Inspect one nonempty source word')
        return [{'rule': list(rule), 'anchors': list(anchors), 'support_lexemes': len(self._evidence[rule])}
                for rule, anchors in self._recoveries(word)]

    def word_candidates(self, word):
        self._check()
        base = self.base
        if word in base.lexicon:
            return base.word_candidates(word)
        votes, evidence = Counter(), {}
        for rule, anchors in self._recoveries(word):
            source_side, remove, append, target_side, remove_gloss, append_gloss = rule
            support = len(self._evidence[rule])
            weight = support/(1+.1*(len(remove)+len(append)+len(remove_gloss)+len(append_gloss)))
            for anchor in anchors:
                counts = base.lexicon[anchor]
                total = sum(counts.values())
                for gloss, count in counts.items():
                    proposed = transform(gloss, target_side, remove_gloss, append_gloss)
                    if not proposed or lexical_key(proposed) != base._gloss_keys[gloss]:
                        continue
                    votes[proposed] += weight*(count/total)
                    evidence[proposed] = {'kind': 'internal_rule' if source_side == 'internal' else 'rule',
                                          'anchor': anchor, 'rule': list(rule), 'support_lexemes': support}
        return [{'gloss': gloss, 'score': votes[gloss], **evidence[gloss]}
                for gloss in sorted(votes, key=lambda gloss: (-votes[gloss], gloss))[:5]]

    def predict(self, example):
        self._check()
        if not isinstance(example, TextExample):
            raise TypeError('Overlay prediction accepts public source words only')
        result = []
        for word in example.tokens:
            candidates = self.word_candidates(word)
            result.append({'gloss': candidates[0]['gloss'] if candidates else None,
                           'candidates': candidates, 'known_form': word in self.base.lexicon})
        return result

    def diagnostics(self):
        self._check()
        baseline = set(self.base._rules())
        selected = set(self._rules)
        return {'algorithm_id': ALGORITHM_ID, 'base_version': self.base.version,
                'total_rule_budget': self.base.max_rules, 'paradigm_window': self.base.paradigm_window,
                'base_hypotheses': len(self.base.rule_evidence),
                'internal_hypotheses': len(self._internal_evidence), 'selected_rules': len(self._rules),
                'selected_internal_rules': sum(rule[0] == 'internal' for rule in self._rules),
                'baseline_rules_displaced': len(baseline-selected)}

    @classmethod
    def from_checkpoint(cls, path):
        """Reuse the base schema; no experimental pickle/checkpoint format."""
        return cls(GlossLearner.load(path))
