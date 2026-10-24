import copy
import json
import tempfile
import unittest
from pathlib import Path
from decipher.generator import episode, Example
from decipher.learner import RuleLearner, AnalogyLearner
from decipher.teacher import Session
from decipher.evaluate import accuracy

class CoreTests(unittest.TestCase):
    def test_transfer_and_contrasting_orders(self):
        for preset in 'ABC':
            _, roots, support, stream, probes = episode(preset)
            learner = RuleLearner(roots)
            before = accuracy(learner, probes)
            learner.correct(support[0].example.source, support[0].meaning)
            self.assertGreater(accuracy(learner, probes), before)
            for gold in support[1:] + stream[:10]:
                learner.correct(gold.example.source, gold.meaning)
            self.assertEqual(accuracy(learner, probes), 1)

    def test_analogy_copies_without_mutation(self):
        learner = AnalogyLearner({})
        meaning = {'agent': 'BIRD'}
        learner.correct('tal mir', meaning)
        prediction = learner.predict('tal mirum')
        self.assertEqual(prediction['meaning'], meaning)
        self.assertFalse(prediction['recall'])
        prediction['meaning']['agent'] = 'TREE'
        self.assertEqual(learner.memory['tal mir'], meaning)

    def test_distinct_presets_and_support_progress(self):
        from decipher.evaluate import evaluate
        grammars = [episode(preset)[0] for preset in 'ABC']
        self.assertEqual(len({tuple(g.roots.items()) for g in grammars}), 3)
        self.assertEqual(len({g.plural for g in grammars}), 3)
        with tempfile.TemporaryDirectory() as tmp:
            report = evaluate(Path(tmp)/'results.json', delay=3)
        self.assertEqual(len(report['runs']), 27)
        for run in report['runs']:
            self.assertEqual([p['labels'] for p in run['support_curve']], list(range(10)))
            self.assertEqual(run['pending'], 3)
            self.assertEqual(run['curve'][-1]['labels'], 57)
            if run['model'] == 'rules':
                self.assertGreater(run['support_curve'][-1]['accuracy'], run['root_only_accuracy'])

    def test_marker_reversal_fresh_start(self):
        from decipher.stress import marker_reversal
        report = marker_reversal()
        self.assertEqual(len(report['runs']), 6)
        for row in report['runs']:
            self.assertTrue(row['fresh_start'])
            self.assertEqual(row['probe_correct'], row['probe_count'])
        for normal, reversed_run in zip(report['runs'][::2], report['runs'][1::2]):
            normal_rules = normal['rules'][0]['rules']
            reversed_rules = reversed_run['rules'][0]['rules']
            self.assertEqual(set(normal_rules), set(reversed_rules))
            self.assertTrue(all(normal_rules[marker] != reversed_rules[marker] for marker in normal_rules))

    def test_checkpoint_identity_and_schema(self):
        from decipher.dataset import identity
        _, roots, support, _, _ = episode()
        metadata = identity('A', 7)
        session = Session(roots, identity=metadata)
        session.predict(support[0].example)
        session.feedback(support[0].example.id, support[0].meaning)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'checkpoint.json'
            session.save(path)
            restored = Session.load(path, expected_identity=metadata)
            self.assertEqual(session.learner.__dict__, restored.learner.__dict__)
            with self.assertRaisesRegex(ValueError, 'identity'):
                Session.load(path, expected_identity=identity('B', 7))
            state = json.loads(path.read_text())
            state['checkpoint_version'] = 99
            path.write_text(json.dumps(state))
            with self.assertRaisesRegex(ValueError, 'version'):
                Session.load(path)
            self.assertEqual(list(Path(tmp).glob('*.tmp')), [])

    def test_manifest_export_is_reproducible_and_separates_answers(self):
        from decipher.dataset import export_dataset, manifest
        with tempfile.TemporaryDirectory() as tmp:
            metadata = export_dataset(tmp)
            self.assertEqual(metadata, manifest('A', 7))
            for split, count in (('support', 9), ('stream', 60), ('probes', 30)):
                records = [json.loads(line) for line in (Path(tmp)/f'{split}.jsonl').read_text().splitlines()]
                self.assertEqual(len(records), count)
                self.assertTrue(all(set(record) == {'id', 'source'} for record in records))
            self.assertEqual(len((Path(tmp)/'teacher-only.jsonl').read_text().splitlines()), 99)

    def test_saved_events_reproduce_first_prediction_metrics(self):
        from decipher.evaluate import evaluate
        with tempfile.TemporaryDirectory() as tmp:
            report = evaluate(Path(tmp)/'results.json', event_directory=Path(tmp)/'events')
            for row in report['runs']:
                events = [json.loads(line) for line in Path(row['event_log']).read_text().splitlines()]
                _, _, _, stream, _ = episode(row['preset'], row['seed'])
                answers = {g.example.id: g.meaning for g in stream}
                predictions = [e for e in events if e['type'] == 'prediction' and e['id'] in answers]
                measured = sum(e['prediction']['meaning'] == answers[e['id']] for e in predictions)/len(predictions)
                self.assertEqual(measured, row['stream_accuracy'])
                self.assertTrue(0 <= row['auc'] <= 1)
                self.assertEqual(row['teacher_answers'], 69)

    def test_invalid_teacher_answer_cannot_mutate_session(self):
        _, roots, support, _, _ = episode()
        session = Session(roots)
        session.predict(support[0].example)
        state = copy.deepcopy(session.__dict__)
        for invalid in ({}, dict(support[0].meaning, tense='FUTURE'), dict(support[0].meaning, agent='UNKNOWN')):
            with self.assertRaises(ValueError):
                session.feedback(support[0].example.id, invalid)
        self.assertEqual(session.learner.__dict__, state['learner'].__dict__)
        self.assertEqual(session.events, state['events'])
        self.assertEqual(session.pending, [])
        self.assertEqual(session.processed, set())

    def test_custom_sentence_cli_and_resume(self):
        import subprocess
        import sys
        import os
        from decipher.meaning import FIELDS
        _, _, support, _, _ = episode()
        gold = support[0]
        answer = ' '.join(gold.meaning[field] for field in FIELDS)
        commands = f'predict {gold.example.source}\ncorrect\nanswer invalid\nanswer {answer}\nsave\nload\npredict {gold.example.source}\nquit\n'
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
            result = subprocess.run([sys.executable, '-m', 'decipher.app', 'demo'], input=commands, text=True, capture_output=True, cwd=tmp, env=env, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Invalid answer:', result.stdout)
            self.assertIn('Checkpoint restored.', result.stdout)
            self.assertIn('Verified memory recall', result.stdout)
            state = json.loads((Path(tmp)/'checkpoint.json').read_text())
            self.assertEqual(len(state['memory']), 1)
            self.assertEqual(state['version'], 1)

    def test_plural_transfer(self):
        learner = RuleLearner({'tal': 'TREE', 'mir': 'BIRD', 'vek': 'SEE', 'kat': 'CAT'})
        meaning = dict(agent='TREE', patient='CAT', predicate='SEE', tense='PRESENT', agent_number='PLURAL', patient_number='SINGULAR')
        self.assertIsNone(learner.predict('mirum vek kat')['meaning'])
        learner.correct('talum vek kat', meaning)
        expected = dict(meaning, agent='BIRD')
        self.assertEqual(learner.predict('mirum vek kat')['meaning'], expected)

    def test_no_probe_mutation_or_gold_leak(self):
        _, roots, support, _, probes = episode()
        session = Session(roots)
        saved = copy.deepcopy(session.predict(support[0].example))
        state = copy.deepcopy(session.__dict__)
        accuracy(session.learner, probes)
        self.assertEqual(session.learner.__dict__, state['learner'].__dict__)
        self.assertEqual({k: v for k, v in session.__dict__.items() if k != 'learner'}, {k: v for k, v in state.items() if k != 'learner'})
        # Replace the evaluator's private answer after prediction; public input is identical.
        from decipher.generator import GoldExample
        altered = GoldExample(support[0].example, dict(support[0].meaning, tense='PAST'))
        independent = Session(roots)
        self.assertEqual(independent.predict(altered.example), saved)
        self.assertEqual(saved, session.events[0]['prediction'])
        session.feedback(support[0].example.id, support[0].meaning)
        self.assertEqual(saved, session.events[0]['prediction'])

    def test_reset_and_disjoint_sets(self):
        for preset in 'ABC':
            spec, roots, support, stream, probes = episode(preset)
            sets = [{x.example.source for x in group} for group in (support, stream, probes)]
            self.assertFalse(sets[0] & sets[1] or sets[0] & sets[2] or sets[1] & sets[2])
            session = Session(roots)
            session.predict(support[0].example)
            session.feedback(support[0].example.id, support[0].meaning)
            fresh = Session(roots)
            self.assertEqual(fresh.learner.version, 0)
            self.assertEqual(len(fresh.learner.hypotheses), 18)
            self.assertTrue(all(spec.render(x.meaning) == x.example.source for x in support + stream + probes))

    def test_delay_idempotence_resume(self):
        _, roots, support, stream, _ = episode()
        session = Session(roots)
        gold = support[0]
        session.predict(gold.example)
        session.feedback(gold.example.id, gold.meaning, 3)
        session.feedback(gold.example.id, gold.meaning, 3)
        self.assertEqual(session.learner.version, 0)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'state.json'
            session.save(path)
            restored = Session.load(path)
            for item in stream[:3]:
                self.assertEqual(session.predict(item.example), restored.predict(item.example))
            self.assertEqual(session.events, restored.events)
            self.assertEqual(session.learner.version, 1)
            self.assertFalse(session.pending)

if __name__ == '__main__':
    unittest.main()
