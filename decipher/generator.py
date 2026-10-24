"""Private synthetic grammars and deterministic, disjoint datasets."""
from dataclasses import dataclass
from itertools import product
import random

NOUNS = ('BIRD', 'TREE', 'CAT', 'DOG', 'FISH', 'CHILD', 'STONE', 'FLOWER')
VERBS = ('SEE', 'CHASE', 'TOUCH')
ORDERS = ('SVO', 'SOV', 'VSO', 'VOS', 'OSV', 'OVS')
PRESETS = {'A': ('SVO', 'suffix'), 'B': ('SOV', 'prefix'), 'C': ('VSO', 'particle')}

@dataclass(frozen=True)
class Example:
    id: str
    source: str

@dataclass(frozen=True)
class GoldExample:
    example: Example
    meaning: dict

@dataclass
class LanguageSpec:
    roots: dict
    order: str
    placement: str
    plural: str
    past: str

    def render(self, meaning):
        def mark(root, marker, enabled):
            if not enabled:
                return root
            if self.placement == 'prefix':
                return marker + root
            if self.placement == 'suffix':
                return root + marker
            return marker + ' ' + root
        parts = {
            'S': mark(self.roots[meaning['agent']], self.plural, meaning['agent_number'] == 'PLURAL'),
            'O': mark(self.roots[meaning['patient']], self.plural, meaning['patient_number'] == 'PLURAL'),
            'V': mark(self.roots[meaning['predicate']], self.past, meaning['tense'] == 'PAST'),
        }
        return ' '.join(parts[role] for role in self.order)


def episode(preset='A', seed=7):
    rng = random.Random(seed * 31 + ord(preset))
    forms = [a+b for a in ('ba', 'ki', 'lo', 'mu', 'ne', 'po') for b in ('ta', 'ri', 'su', 've')]
    rng.shuffle(forms)
    roots = dict(zip(NOUNS + VERBS, forms))
    order, placement = PRESETS[preset]
    plural, past = {'A': ('za', 'xu'), 'B': ('fe', 'wo'), 'C': ('jo', 'ha')}[preset]
    spec = LanguageSpec(roots, order, placement, plural, past)
    meanings = [dict(agent=a, predicate=v, patient=o, tense=t, agent_number=s, patient_number=p)
                for a, v, o, t, s, p in product(NOUNS, VERBS, NOUNS, ('PRESENT', 'PAST'), ('SINGULAR', 'PLURAL'), ('SINGULAR', 'PLURAL')) if a != o]
    rng.shuffle(meanings)
    examples = [GoldExample(Example(f'{preset}-{seed}-{i}', spec.render(m)), m) for i, m in enumerate(meanings[:99])]
    return spec, {form: concept for concept, form in roots.items()}, examples[:9], examples[9:69], examples[69:99]


def english(m):
    if not m:
        return 'Unknown — more teacher evidence needed'
    return f"{m['agent'].lower()} ({m['agent_number'].lower()}) {m['predicate'].lower()} [{m['tense'].lower()}] {m['patient'].lower()} ({m['patient_number'].lower()})"
