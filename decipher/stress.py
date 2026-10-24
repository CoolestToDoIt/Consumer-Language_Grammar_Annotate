"""Paired marker reversal: shared forms, opposing meanings, fresh learners."""
from dataclasses import replace
from .generator import episode
from .learner import RuleLearner
from .evaluate import accuracy


def marker_reversal():
    results = []
    for preset in 'ABC':
        spec, roots, support, _, probes = episode(preset)
        for reversed_markers in (False, True):
            grammar = replace(spec, plural=spec.past, past=spec.plural) if reversed_markers else spec
            learner = RuleLearner(roots)
            fresh = learner.version == 0 and not learner.memory and len(learner.hypotheses) == 18
            for gold in support:
                learner.correct(grammar.render(gold.meaning), gold.meaning)
            correct = sum(learner.predict(grammar.render(gold.meaning))['meaning'] == gold.meaning for gold in probes)
            results.append({'preset': preset, 'reversed': reversed_markers, 'fresh_start': fresh,
                            'probe_correct': correct, 'probe_count': len(probes), 'accuracy': correct/len(probes),
                            'rules': learner.hypotheses})
    return {'protocol': 'Paired languages share roots and sentence meanings, but swap plural/past marker strings. Each learner starts fresh; nine support labels; 30 held-out probes.', 'runs': results}
