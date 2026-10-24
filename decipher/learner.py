"""Learners receive released roots and corrected pairs, never a LanguageSpec."""
from itertools import product
import copy
from .generator import ORDERS, VERBS

class MemoryLearner:
    def __init__(self, roots):
        self.roots = dict(roots)
        self.memory = {}
        self.version = 0

    def correct(self, source, meaning):
        if self.memory.get(source) != meaning:
            self.memory[source] = copy.deepcopy(meaning)
            self.version += 1

    def predict(self, source):
        m = self.memory.get(source)
        return {'meaning': copy.deepcopy(m), 'candidates': [copy.deepcopy(m)] if m else [], 'version': self.version, 'recall': m is not None}

class RuleLearner(MemoryLearner):
    def __init__(self, roots):
        super().__init__(roots)
        self.hypotheses = []
        self._fit()

    def _segments(self, source, placement):
        result, pending = [], None
        for token in source.split():
            matches = []
            for root, concept in self.roots.items():
                if token == root:
                    matches.append((concept, pending if placement == 'particle' else None))
                elif placement == 'prefix' and token.endswith(root):
                    matches.append((concept, token[:-len(root)]))
                elif placement == 'suffix' and token.startswith(root):
                    matches.append((concept, token[len(root):]))
            if len(matches) == 1:
                result.append(matches[0]); pending = None
            elif placement == 'particle' and not matches and pending is None:
                pending = token
            else:
                return None
        return result if len(result) == 3 and pending is None else None

    def _decode(self, source, order, placement, rules):
        segments = self._segments(source, placement)
        if segments is None:
            return None
        m = {'tense': 'PRESENT', 'agent_number': 'SINGULAR', 'patient_number': 'SINGULAR'}
        for role, (concept, marker) in zip(order, segments):
            if (role == 'V') != (concept in VERBS):
                return None
            slot = {'S': 'agent', 'O': 'patient', 'V': 'predicate'}[role]
            m[slot] = concept
            if marker:
                feature = rules.get(marker)
                if feature != ('PAST' if role == 'V' else 'PLURAL'):
                    return None
                m['tense' if role == 'V' else slot + '_number'] = feature
        return m

    def _fit(self):
        self.hypotheses = []
        for order, placement in product(ORDERS, ('prefix', 'suffix', 'particle')):
            rules, valid = {}, True
            for source, meaning in self.memory.items():
                segments = self._segments(source, placement)
                if segments is None:
                    valid = False; break
                for role, (concept, marker) in zip(order, segments):
                    slot = {'S': 'agent', 'O': 'patient', 'V': 'predicate'}[role]
                    feature = meaning['tense' if role == 'V' else slot + '_number']
                    if concept != meaning[slot] or (not marker and feature in ('PAST', 'PLURAL')) or (marker and feature in ('PRESENT', 'SINGULAR')):
                        valid = False; break
                    if marker:
                        if marker in rules and rules[marker] != feature:
                            valid = False; break
                        rules[marker] = feature
                if not valid:
                    break
            if valid:
                self.hypotheses.append({'order': order, 'placement': placement, 'rules': rules})

    def correct(self, source, meaning):
        super().correct(source, meaning)
        self._fit()

    def predict(self, source):
        result = super().predict(source)
        if result['recall']:
            return result
        votes = {}
        for h in self.hypotheses:
            m = self._decode(source, **h)
            if m:
                key = tuple(sorted(m.items()))
                votes[key] = votes.get(key, 0) + 1
        ranked = sorted(votes, key=lambda k: (-votes[k], k))
        result.update(meaning=dict(ranked[0]) if ranked else None, candidates=[dict(k) for k in ranked[:5]], agreement=(votes[ranked[0]] / len(self.hypotheses)) if ranked else 0)
        return result


class AnalogyLearner(MemoryLearner):
    """Copy the closest corrected sentence by character-trigram Jaccard score."""
    @staticmethod
    def _grams(text):
        padded = '^^' + text + '$$'
        return {padded[i:i+3] for i in range(len(padded)-2)}

    def predict(self, source):
        result = super().predict(source)
        if result['recall'] or not self.memory:
            return result
        query = self._grams(source)
        def score(known):
            grams = self._grams(known)
            return len(query & grams) / len(query | grams)
        nearest = min(self.memory, key=lambda known: (-score(known), known))
        meaning = copy.deepcopy(self.memory[nearest])
        result.update(meaning=meaning, candidates=[copy.deepcopy(meaning)], similarity=score(nearest))
        return result
