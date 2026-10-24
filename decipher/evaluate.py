import json
from pathlib import Path
from time import perf_counter
import platform
import sys
from .generator import episode, PRESETS
from .teacher import Session
from .dataset import identity, manifest


def accuracy(learner, examples):
    return sum(learner.predict(x.example.source)['meaning'] == x.meaning for x in examples) / len(examples)


def evaluate(output='results.json', delay=0, event_directory=None):
    if delay < 0:
        raise ValueError('Delay must be nonnegative')
    rows = []
    manifests = []
    if event_directory is not None:
        event_directory = Path(event_directory)
        event_directory.mkdir(parents=True, exist_ok=True)
    for preset in PRESETS:
        for seed in (7, 19, 41):
            _, roots, support, stream, probes = episode(preset, seed)
            manifests.append(manifest(preset, seed))
            for model in ('memory', 'analogy', 'rules'):
                session = Session(roots, model, identity=identity(preset, seed))
                prediction_seconds, update_seconds = [], []
                root_only_accuracy = accuracy(session.learner, probes)
                support_curve = [{'labels': 0, 'accuracy': root_only_accuracy}]
                for gold in support:
                    session.predict(gold.example)
                    session.feedback(gold.example.id, gold.meaning)
                    support_curve.append({'labels': len(session.processed), 'accuracy': accuracy(session.learner, probes)})
                curve = [{'labels': 0, 'accuracy': accuracy(session.learner, probes)}]
                correct = 0
                for i, gold in enumerate(stream, 1):
                    start = perf_counter()
                    prediction = session.predict(gold.example)
                    prediction_seconds.append(perf_counter() - start)
                    correct += prediction['meaning'] == gold.meaning
                    start = perf_counter()
                    session.feedback(gold.example.id, gold.meaning, delay)
                    update_seconds.append(perf_counter() - start)
                    if i in (5, 10, 20, 40, 60):
                        curve.append({'labels': len(session.processed) - len(support), 'accuracy': accuracy(session.learner, probes)})
                combined_curve = support_curve + [{'labels': p['labels'] + len(support), 'accuracy': p['accuracy']} for p in curve[1:]]
                budget = combined_curve[-1]['labels']
                auc = sum((b['labels'] - a['labels']) * (a['accuracy'] + b['accuracy']) / 2 for a, b in zip(combined_curve, combined_curve[1:])) / budget
                event_log = None
                if event_directory is not None:
                    event_log = str(event_directory / f'{preset}-{seed}-{model}.jsonl')
                    session.export(event_log)
                rows.append(dict(auc=auc, event_log=event_log, prediction_ms=sum(prediction_seconds)/len(prediction_seconds)*1000, feedback_call_ms=sum(update_seconds)/len(update_seconds)*1000, teacher_answers=len(session.processed), teacher_decisions=len(support)+len(stream), preset=preset, seed=seed, model=model, delay=delay, root_only_accuracy=root_only_accuracy, support_labels=len(support), support_curve=support_curve, curve=curve, stream_accuracy=correct/len(stream), pending=len(session.pending), retention=accuracy(session.learner, support)))
    report = {'protocol': '11 root anchors + 9 support sentences; 60 stream sentences; 30 disjoint never-taught probes. Pending labels are not drained.', 'environment': {'python': sys.version.split()[0], 'platform': platform.platform()}, 'manifests': manifests, 'runs': rows}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(report, indent=2))
    return report
