import copy
import importlib.util
from pathlib import Path
import random
import tempfile
import unittest

HAS_TORCH = importlib.util.find_spec('torch') is not None


def equivalent(left, right):
    import torch
    if isinstance(left, torch.Tensor):
        return isinstance(right, torch.Tensor) and torch.equal(left.cpu(), right.cpu())
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equivalent(left[k], right[k]) for k in left)
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(equivalent(a, b) for a, b in zip(left, right))
    return left == right


@unittest.skipUnless(HAS_TORCH, 'Optional neural dependency is not installed')
class NeuralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        torch.set_num_threads(1)

    def learner(self, mode='hybrid', **kwargs):
        from decipher.neural import NeuralConfig, NeuralLearner
        return NeuralLearner(NeuralConfig(embedding=8, hidden=12, update_steps=1, replay_batch=2,
                                         reservoir_size=3, max_source_bytes=64, max_target_bytes=32, **kwargs), mode)

    def test_model_can_fit_a_corrected_pair_without_memory(self):
        learner = self.learner(mode='parameters', learning_rate=.03)
        for i in range(45):
            learner.correct(str(i), 'mir', 'BIRD')
        prediction = learner.predict('mir', beam_size=1, max_bytes=12, use_memory=False)
        self.assertEqual(prediction['text'], 'BIRD')
        self.assertFalse(prediction['recall'])

    def test_modes_change_only_authorized_state(self):
        for mode in ('frozen', 'memory', 'parameters', 'replay', 'hybrid'):
            learner = self.learner(mode)
            initial = copy.deepcopy(learner.network.state_dict())
            learner.correct('one', 'mir', 'BIRD')
            learned = not equivalent(initial, learner.network.state_dict())
            self.assertEqual(learned, mode in ('parameters', 'replay', 'hybrid'))
            result = learner.predict('mir', max_bytes=5, beam_size=1)
            self.assertEqual(result['recall'], mode in ('memory', 'hybrid'))

    def test_prediction_and_construction_preserve_rng_and_fitted_state(self):
        import torch
        before_torch = torch.get_rng_state().clone()
        before_python = random.getstate()
        learner = self.learner()
        self.assertTrue(torch.equal(before_torch, torch.get_rng_state()))
        self.assertEqual(before_python, random.getstate())
        learner.correct('one', 'mir', 'BIRD')
        before = copy.deepcopy(learner.state())
        learner.predict('tal', beam_size=2, max_bytes=8)
        self.assertTrue(equivalent(before, learner.state()))
        self.assertTrue(torch.equal(before_torch, torch.get_rng_state()))
        self.assertEqual(before_python, random.getstate())

    def test_duplicate_revision_and_fresh_start(self):
        learner = self.learner()
        learner.correct('one', 'mir', 'BIRD')
        steps = learner.optimizer_steps
        self.assertFalse(learner.correct('one', 'mir', 'BIRD'))
        self.assertEqual(steps, learner.optimizer_steps)
        learner.correct('one', 'mir', 'TREE')
        authoritative = self.learner()
        authoritative.correct('one', 'mir', 'TREE')
        self.assertTrue(equivalent(learner.network.state_dict(), authoritative.network.state_dict()))
        self.assertTrue(equivalent(learner.optimizer.state_dict(), authoritative.optimizer.state_dict()))
        self.assertEqual(learner.predict('mir')['text'], 'TREE')
        fresh = self.learner()
        self.assertEqual(fresh.version, 0)
        self.assertEqual(fresh.records, {})
        self.assertEqual(fresh.reservoir, [])

    def test_resume_replays_identical_optimizer_and_reservoir_updates(self):
        learner = self.learner()
        for i in range(5):
            learner.correct(str(i), f'word{i}', f'MEANING{i}')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'model.pt'
            learner.save(path)
            from decipher.neural import NeuralLearner
            resumed = NeuralLearner.load(path)
        for i in range(5, 9):
            learner.correct(str(i), f'word{i}', f'MEANING{i}')
            resumed.correct(str(i), f'word{i}', f'MEANING{i}')
        self.assertTrue(equivalent(learner.network.state_dict(), resumed.network.state_dict()))
        self.assertTrue(equivalent(learner.optimizer.state_dict(), resumed.optimizer.state_dict()))
        self.assertEqual(learner.reservoir, resumed.reservoir)
        self.assertEqual(learner.rng.getstate(), resumed.rng.getstate())
        self.assertEqual(learner.training_examples_consumed, resumed.training_examples_consumed)

    def test_delayed_answers_and_session_resume_never_rewrite_predictions(self):
        from decipher.online import OnlineSession
        session = OnlineSession(self.learner(), 'test-language')
        saved = session.predict('one', 'mir', beam_size=1, max_bytes=6)
        session.feedback('one', 'BIRD', delay=3)
        original = copy.deepcopy(session.events[0]['prediction'])
        self.assertEqual(session.learner.version, 0)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'session.pt'
            session.save(path)
            resumed = OnlineSession.load(path)
        for i in range(3):
            self.assertEqual(session.predict(f'next{i}', f'input{i}', beam_size=1, max_bytes=6), resumed.predict(f'next{i}', f'input{i}', beam_size=1, max_bytes=6))
        self.assertEqual(session.learner.version, 1)
        self.assertFalse(session.pending)
        self.assertEqual(saved, original)
        self.assertEqual(session.events[0]['prediction'], original)
        self.assertTrue(equivalent(session.learner.network.state_dict(), resumed.learner.network.state_dict()))
        self.assertFalse(session.feedback('one', 'BIRD', revision=0))
        with self.assertRaisesRegex(ValueError, 'higher revision'):
            session.feedback('one', 'TREE', revision=0)
        session.feedback('one', 'TREE', revision=1)
        self.assertEqual(session.learner.predict('mir')['text'], 'TREE')
        self.assertEqual(session.events[0]['prediction'], original)

    def test_invalid_or_oversize_feedback_cannot_change_state(self):
        learner = self.learner()
        before = copy.deepcopy(learner.state())
        with self.assertRaises(ValueError):
            learner.correct('x', 'valid', 'x'*100)
        self.assertTrue(equivalent(before, learner.state()))
        with self.assertRaises(ValueError):
            learner.predict('x'*100)

if __name__ == '__main__':
    unittest.main()
