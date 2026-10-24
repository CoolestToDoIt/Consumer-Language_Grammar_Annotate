"""Feature-2 contract and complete standard-library teaching flows."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from decipher.corpus import TextExample
from decipher.teaching import ProjectConflict, RevisionConflict, TeachingService, public_example
from decipher.teaching_fixture import FixtureProjectStore


class TeachingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.path = self.directory/'project.fixture.json'
        self.store = FixtureProjectStore()
        self.project = self.store.create(self.path, name='Language lessons', language='Fixture')
        self.service = TeachingService(self.project)

    def lesson(self, identifier, text, glosses):
        self.service.submit(identifier, text)
        prediction = self.service.predict(identifier)
        return self.service.correct(prediction['prediction_id'], glosses), prediction

    def test_correction_transfers_and_reopen_preserves_original_predictions(self):
        result, anchors = self.lesson('anchors', 'tal mir', ['tree', 'bird'])
        self.service.submit('probe', 'mirum')
        before = self.service.predict('probe')
        self.assertIsNone(before['words'][0]['gloss'])
        self.lesson('plural', 'talum', ['tree-PL'])
        current = self.service.predict('probe')
        self.assertEqual(current['words'][0]['gloss'], 'bird-PL')
        result = self.service.confirm(current['prediction_id'], operation_id='confirm-once')
        self.assertEqual(result['correction']['revision'], 1)
        restored = self.store.open(self.path)
        self.assertEqual(restored.prediction(before['prediction_id']), before)
        self.assertEqual(restored.prediction(anchors['prediction_id']), anchors)
        self.assertEqual(restored.learner.__dict__, self.project.learner.__dict__)
        self.assertEqual(restored.history('probe'), self.project.history('probe'))
        exported = self.directory/'export.fixture.json'
        self.project.export(exported)
        clone = self.store.open(exported)
        self.assertEqual(clone.project_id, self.project.project_id)
        self.assertEqual(clone.model_identity(), self.project.model_identity())
        self.assertEqual(clone.prediction(before['prediction_id']), before)

    def test_unknown_confirmation_and_bad_alignment_do_not_teach(self):
        self.service.submit('unknown', 'tal mir')
        prediction = self.service.predict('unknown')
        before = copy.deepcopy(self.project._state())
        with self.assertRaisesRegex(ValueError, 'unknown words'):
            self.service.confirm(prediction['prediction_id'])
        for values in (['tree'], ['tree', ''], ['tree', None], ['two words', 'bird']):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.service.correct(prediction['prediction_id'], values)
        self.assertEqual(self.project._state(), before)
        self.assertEqual(self.project.model_version, 0)

    def test_provisional_workspace_guesses_require_an_explicit_correction(self):
        from decipher.workspace import WorkspaceStore
        path = self.directory/'production.dproj'
        project = WorkspaceStore().create(path, name='Language', language='Test')
        service = TeachingService(project)
        service.submit('anchor', 'tal')
        anchor = service.predict('anchor')
        service.correct(anchor['prediction_id'], ['tree'])
        service.submit('unknown', 'talum')
        guess = service.predict('unknown')
        word = guess['words'][0]
        self.assertEqual(word['gloss'], 'tree')
        self.assertFalse(word['known_form'])
        self.assertTrue(word['provisional'])
        from decipher.teaching_app import prediction_text
        self.assertIn('[tentative draft form]', prediction_text(guess))
        before = project.model_version
        with self.assertRaisesRegex(ValueError, 'provisional guesses'):
            service.confirm(guess['prediction_id'])
        self.assertEqual(project.model_version, before)
        service.correct(guess['prediction_id'], ['tree-PL'])
        self.assertEqual(project.annotation('unknown')['glosses'], ['tree-PL'])

    def test_two_reviewed_predictions_cannot_overwrite_a_newer_annotation(self):
        self.service.submit('word', 'tal')
        first = self.service.predict('word')
        second = self.service.predict('word')
        self.service.correct(first['prediction_id'], ['tree'])
        before = copy.deepcopy(self.project._state())
        with self.assertRaisesRegex(RevisionConflict, 'current revision 1'):
            self.service.correct(second['prediction_id'], ['bird'], replace=True, reason='stale client')
        self.assertEqual(self.project._state(), before)

    def test_revision_replaces_evidence_and_requires_explicit_reason(self):
        self.lesson('word', 'tal', ['tree'])
        latest = self.service.predict('word')
        for options in ({}, {'replace': True}, {'reason': 'correcting a mistake'}):
            with self.subTest(options=options), self.assertRaises(RevisionConflict):
                self.service.correct(latest['prediction_id'], ['bird'], **options)
        revised = self.service.correct(latest['prediction_id'], ['bird'], replace=True, reason='wrong lexical anchor')
        self.assertEqual(revised['correction']['revision'], 2)
        self.assertEqual(self.project.learner.lexicon['tal'], {'bird': 1})
        self.assertEqual([row['glosses'] for row in self.project.history('word')], [['tree'], ['bird']])
        restored = self.store.open(self.path)
        self.assertEqual(restored.history('word'), self.project.history('word'))
        self.assertEqual(restored.model_identity(), self.project.model_identity())

    def test_operations_are_idempotent_but_cannot_change_meaning(self):
        self.service.submit('word', 'tal')
        prediction = self.service.predict('word')
        first = self.service.correct(prediction['prediction_id'], ['tree'], operation_id='retry-safe')
        second = self.service.correct(prediction['prediction_id'], ['tree'], operation_id='retry-safe')
        self.assertEqual(first['correction'], second['correction'])
        self.assertEqual(self.project.model_version, 1)
        with self.assertRaisesRegex(ValueError, 'different correction'):
            self.service.correct(prediction['prediction_id'], ['bird'], operation_id='retry-safe')
        restored = TeachingService(self.store.open(self.path))
        self.assertEqual(restored.correct(prediction['prediction_id'], ['tree'], operation_id='retry-safe')['correction'], first['correction'])

    def test_confirm_rejects_a_prediction_from_an_older_model(self):
        self.lesson('anchor', 'tal', ['tree'])
        self.service.submit('same-word', 'tal')
        prediction = self.service.predict('same-word')
        self.lesson('other', 'mir', ['bird'])
        before = self.project.model_identity()
        with self.assertRaisesRegex(RevisionConflict, 'Model changed'):
            self.service.confirm(prediction['prediction_id'])
        self.assertEqual(self.project.model_identity(), before)

    def test_normalization_source_identity_and_public_prediction_boundary(self):
        self.service.submit('caf\u00e9', ['cafe\u0301'])
        self.assertFalse(self.service.submit('cafe\u0301', ['caf\u00e9'])['added'])
        with self.assertRaisesRegex(ValueError, 'cannot change source'):
            self.service.submit('caf\u00e9', 'another')
        original = self.project.learner.predict
        def public_only(example):
            self.assertIsInstance(example, TextExample)
            self.assertEqual(set(example.__dict__), {'id', 'tokens'})
            return original(example)
        with patch.object(self.project.learner, 'predict', side_effect=public_only):
            prediction = self.service.predict('cafe\u0301')
        prediction['words'][0]['gloss'] = 'tampered'
        self.assertIsNone(self.project.prediction(prediction['prediction_id'])['words'][0]['gloss'])

    def test_stale_fixture_save_and_failed_write_preserve_saved_work(self):
        stale = TeachingService(self.store.open(self.path))
        self.lesson('word', 'tal', ['tree'])
        saved = self.path.read_bytes()
        with self.assertRaises(ProjectConflict):
            stale.submit('other', 'mir')
        self.assertEqual(self.path.read_bytes(), saved)
        with patch('decipher.teaching_fixture._replace_with_retry', side_effect=OSError('injected write failure')):
            with self.assertRaises(OSError):
                self.service.submit('new', 'vel')
        self.assertEqual(self.path.read_bytes(), saved)
        self.assertEqual(self.store.open(self.path).model_version, 1)
        self.assertFalse(list(self.directory.glob('*.tmp')))

    def test_corrupted_and_wrong_schema_fixture_is_rejected(self):
        content = json.loads(self.path.read_text(encoding='utf-8'))
        content['project']['name'] = 'changed without checksum'
        self.path.write_text(json.dumps(content), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.store.open(self.path)

    def test_foreign_writer_lock_does_not_get_removed_or_overwritten(self):
        lock = self.path.with_name(self.path.name+'.lock')
        lock.write_text('another writer', encoding='utf-8')
        before = self.path.read_bytes()
        with self.assertRaises(ProjectConflict):
            self.project.save()
        self.assertEqual(lock.read_text(encoding='utf-8'), 'another writer')
        self.assertEqual(self.path.read_bytes(), before)

    def test_one_shot_cli_teaches_and_reopens_without_site_packages(self):
        project = self.directory/'cli.fixture.json'
        def cli(*arguments, check=True):
            command = [sys.executable, '-X', 'utf8', '-S', '-m', 'decipher.app', 'gloss', 'teach',
                       *map(str, arguments), '--project', str(project), '--backend', 'fixture', '--json']
            return subprocess.run(command, capture_output=True, text=True, encoding='utf-8', check=check)
        cli('init', '--name', 'CLI language', '--language', 'Test')
        cli('submit', '--id', 'lesson', '--text', 'tal mir')
        before = json.loads(cli('predict', '--id', 'lesson').stdout)
        result = json.loads(cli('correct', '--prediction', before['prediction_id'], '--glosses', 'tree', 'bird').stdout)
        self.assertEqual([row['gloss'] for row in result['after']['words']], ['tree', 'bird'])
        self.assertEqual(json.loads(cli('history', '--id', 'lesson').stdout)[0]['revision'], 1)
        failed = cli('correct', '--prediction', before['prediction_id'], '--glosses', 'bird', check=False)
        self.assertEqual(failed.returncode, 2)
        self.assertIn('aligned', failed.stderr)

    def test_teaching_help_exposes_real_commands_through_the_existing_gloss_entrypoint(self):
        result = subprocess.run([sys.executable, '-X', 'utf8', '-S', '-m', 'decipher.app', 'gloss', 'teach', '--help'],
                                capture_output=True, text=True, encoding='utf-8', check=True)
        self.assertIn('confirm', result.stdout)
        self.assertIn('history', result.stdout)
        self.assertIn('shell', result.stdout)

    def test_interactive_cli_recovers_from_misalignment_then_transfers(self):
        script = ('submit anchors tal mir\npredict anchors\ncorrect tree\ncorrect tree bird\n'
                  'submit plural talum\npredict plural\ncorrect tree-PL\n'
                  'submit probe mirum\npredict probe\nconfirm\nhistory probe\nquit\n')
        command = [sys.executable, '-X', 'utf8', '-S', '-m', 'decipher.teaching_app', 'shell',
                   '--project', str(self.path), '--backend', 'fixture']
        result = subprocess.run(command, input=script, capture_output=True, text=True, encoding='utf-8', check=True)
        self.assertIn('Expected 2 aligned', result.stdout)
        self.assertIn('bird-PL', result.stdout)
        self.assertEqual(self.store.open(self.path).annotation('probe')['glosses'], ['bird-PL'])

    def test_interactive_language_apostrophes_reasons_and_native_paths_are_literal(self):
        exported = self.directory/'backup with spaces.fixture.json'
        script = ("submit sentence don't misread\npredict sentence\ncorrect don't understand\n"
                  "predict sentence\nreplace teacher's correction :: don't know\n"
                  "search teacher's\n"+f'export {exported}\nquit\n')
        result = subprocess.run([sys.executable, '-X', 'utf8', '-S', '-m', 'decipher.teaching_app', 'shell',
                                 '--project', str(self.path), '--backend', 'fixture'], input=script,
                                capture_output=True, text=True, encoding='utf-8', check=True)
        self.assertNotIn('Error:', result.stdout)
        restored = self.store.open(exported)
        self.assertEqual(restored.examples()[0].tokens, ("don't", 'misread'))
        self.assertEqual(restored.annotation('sentence')['glosses'], ["don't", 'know'])
        self.assertEqual(restored.history('sentence')[-1]['reason'], "teacher's correction")


if __name__ == '__main__':
    unittest.main()
