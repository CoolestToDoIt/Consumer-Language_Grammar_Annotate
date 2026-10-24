"""Append-only first predictions, delayed feedback, and portable checkpoints."""
import copy
import json
import os
import tempfile
from pathlib import Path
from .learner import RuleLearner, MemoryLearner, AnalogyLearner
from .meaning import validate

class Session:
    def __init__(self, roots, model='rules', identity=None):
        self.identity = copy.deepcopy(identity)
        self.model = model
        models = {'rules': RuleLearner, 'memory': MemoryLearner, 'analogy': AnalogyLearner}
        if model not in models:
            raise ValueError('Unknown model')
        self.learner = models[model](roots)
        self.step = 0
        self.events = []
        self.pending = []
        self.processed = set()
        self.sources = {}

    def predict(self, example):
        if example.id in self.sources:
            raise ValueError('Example ID already predicted')
        self.step += 1
        self.flush()
        prediction = self.learner.predict(example.source)
        self.sources[example.id] = example.source
        self.events.append(dict(type='prediction', step=self.step, id=example.id, source=example.source, prediction=copy.deepcopy(prediction)))
        return prediction

    def feedback(self, example_id, meaning, delay=0):
        if delay < 0:
            raise ValueError('Delay must be nonnegative')
        if example_id not in self.sources:
            raise ValueError('Predict before requesting feedback')
        meaning = validate(meaning, self.learner.roots)
        if example_id in self.processed or any(e['id'] == example_id for e in self.pending):
            return
        self.pending.append(dict(id=example_id, meaning=copy.deepcopy(meaning), due=self.step + delay))
        self.flush()

    def flush(self):
        remaining = []
        for event in self.pending:
            if event['due'] <= self.step:
                self.learner.correct(self.sources[event['id']], event['meaning'])
                self.processed.add(event['id'])
                self.events.append(dict(type='feedback', step=self.step, **event))
            else:
                remaining.append(event)
        self.pending = remaining

    def save(self, path):
        state = dict(checkpoint_version=1, identity=self.identity, model=self.model, roots=self.learner.roots, memory=self.learner.memory, version=self.learner.version, step=self.step, events=self.events, pending=self.pending, processed=sorted(self.processed), sources=self.sources)
        destination = Path(path)
        with tempfile.NamedTemporaryFile(mode='w', dir=destination.parent, prefix=destination.name + '.', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            try:
                json.dump(state, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        try:
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    @classmethod
    def load(cls, path, expected_identity=None):
        state = json.loads(Path(path).read_text())
        if state.get('checkpoint_version') != 1:
            raise ValueError('Unsupported checkpoint version; start a fresh session')
        if expected_identity is not None and state.get('identity') != expected_identity:
            raise ValueError('Checkpoint dataset identity differs from this episode')
        session = cls(state['roots'], state['model'], identity=state.get('identity'))
        for source, meaning in state['memory'].items():
            session.learner.correct(source, meaning)
        session.learner.version = state['version']
        for key in ('step', 'events', 'pending', 'sources'):
            setattr(session, key, state[key])
        session.processed = set(state['processed'])
        return session

    def export(self, path):
        Path(path).write_text(''.join(json.dumps(event) + '\n' for event in self.events))
