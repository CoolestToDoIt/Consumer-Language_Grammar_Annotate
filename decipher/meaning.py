"""Validate teacher-supplied records before they can change learned state."""
from .generator import NOUNS, VERBS

FIELDS = ('agent', 'predicate', 'patient', 'tense', 'agent_number', 'patient_number')


def validate(meaning, roots):
    if not isinstance(meaning, dict) or set(meaning) != set(FIELDS):
        raise ValueError('Answer must contain exactly: ' + ', '.join(FIELDS))
    allowed = {'agent': NOUNS, 'predicate': VERBS, 'patient': NOUNS,
               'tense': ('PRESENT', 'PAST'), 'agent_number': ('SINGULAR', 'PLURAL'), 'patient_number': ('SINGULAR', 'PLURAL')}
    for slot, choices in allowed.items():
        if not isinstance(meaning[slot], str) or meaning[slot] not in choices:
            raise ValueError(f'{slot} must be one of: {", ".join(choices)}')
    for slot in ('agent', 'predicate', 'patient'):
        if meaning[slot] not in roots.values():
            raise ValueError(f'{meaning[slot]} is not an anchored concept in this language')
    return {field: meaning[field] for field in FIELDS}


def parse_answer(text, roots):
    parts = text.upper().split()
    if len(parts) != 6:
        raise ValueError('Use: answer AGENT VERB PATIENT PRESENT/PAST SINGULAR/PLURAL SINGULAR/PLURAL')
    return validate(dict(zip(FIELDS, parts)), roots)
