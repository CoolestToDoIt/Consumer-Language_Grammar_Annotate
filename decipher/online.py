"""Model-independent prediction-before-feedback sessions for text targets."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile


def validate_text(text, limit):
    if not isinstance(text, str) or not text or len(text.encode('utf-8')) > limit:
        raise ValueError(f'Text must be nonempty and at most {limit} UTF-8 bytes')


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class OnlineSession:
    def __init__(self, learner, language_id='unspecified'):
        self.learner = learner
        self.language_id = language_id
        self.step = 0
        self.sources = {}
        self.events = []
        self.pending = []
        self.processed = {}

    def _event(self, kind, **values):
        return {'schema_version': 1, 'language_id': self.language_id, 'event_type': kind,
                'step': self.step, 'timestamp': timestamp(), **values}

    def predict(self, identifier, source, **kwargs):
        if not isinstance(identifier, str) or not identifier or identifier in self.sources:
            raise ValueError('Prediction ID must be a new nonempty string')
        # Validate before advancing time or exposing already-due labels.
        validate_text(source, self.learner.config.max_source_bytes)
        self.step += 1
        self.flush()
        prediction = self.learner.predict(source, **kwargs)
        self.sources[identifier] = source
        self.events.append(self._event('prediction', example_id=identifier, source=source, model_version=self.learner.version, prediction=copy.deepcopy(prediction)))
        return prediction

    def feedback(self, identifier, target, delay=0, revision=0):
        if identifier not in self.sources:
            raise ValueError('Predict an example before scheduling feedback')
        if not isinstance(delay, int) or delay < 0 or not isinstance(revision, int) or revision < 0:
            raise ValueError('Delay and revision must be nonnegative integers')
        validate_text(target, self.learner.config.max_target_bytes)
        incoming = {'example_id': identifier, 'target': target, 'arrival_step': self.step+delay, 'feedback_revision': revision}
        previous = self.processed.get(identifier)
        queued = next((event for event in self.pending if event['example_id'] == identifier), None)
        latest = queued or previous
        if latest:
            if revision < latest['feedback_revision']:
                raise ValueError('Feedback revision is older than the current annotation')
            if revision == latest['feedback_revision']:
                if latest['target'] != target:
                    raise ValueError('Conflicting label needs a higher revision number')
                return False
        # A revision supersedes a queued older answer; historical applied events stay.
        self.pending = [event for event in self.pending if event['example_id'] != identifier]
        self.pending.append(incoming)
        self.flush()
        return True

    def flush(self):
        # Stable arrival ordering is preserved across checkpoint/restart.
        due = sorted((e for e in self.pending if e['arrival_step'] <= self.step), key=lambda e: e['arrival_step'])
        for event in due:
            identifier = event['example_id']
            self.learner.correct(identifier, self.sources[identifier], event['target'])
            self.processed[identifier] = copy.deepcopy(event)
            self.events.append(self._event('feedback', model_version=self.learner.version, **event))
            self.pending.remove(event)

    def state(self):
        return {'schema_version': 1, 'language_id': self.language_id, 'step': self.step,
                'sources': dict(self.sources), 'events': copy.deepcopy(self.events),
                'pending': copy.deepcopy(self.pending), 'processed': copy.deepcopy(self.processed)}

    def save(self, path):
        import torch
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
        try:
            torch.save({'session': self.state(), 'learner': self.learner.state()}, temporary)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    @classmethod
    def load(cls, path, device='cpu'):
        import torch
        from .neural import NeuralLearner
        state = torch.load(path, map_location='cpu', weights_only=True)
        session_state = state['session']
        if session_state.get('schema_version') != 1:
            raise ValueError('Unsupported online session schema')
        learner = NeuralLearner.from_state(state['learner'], device=device)
        session = cls(learner, session_state['language_id'])
        for key in ('step', 'sources', 'events', 'pending', 'processed'):
            setattr(session, key, session_state[key])
        return session

    def export(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        for kind in ('prediction', 'feedback'):
            (directory/('predictions.jsonl' if kind == 'prediction' else 'feedback.jsonl')).write_text(''.join(json.dumps(event, ensure_ascii=False)+'\n' for event in self.events if event['event_type'] == kind))
