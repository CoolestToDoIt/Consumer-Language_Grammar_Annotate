"""B's real CLI/review flow on A's .dproj format and web/storage conflict guards."""
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from decipher.corpus import TextExample
from decipher.gloss import GlossLearner
from decipher.gloss_web import GlossWebApp
from decipher.project import LanguageProject, AnnotationRevisionConflict, ProjectWriteConflict
from decipher.review import review_queue, search
from decipher.teaching import ProjectConflict, RevisionConflict, TeachingService, learner_identity
from decipher.workspace import WorkspaceStore


class WorkspaceTeachingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.path = self.directory/'language.dproj'
        self.store = WorkspaceStore()
        self.project = self.store.create(self.path, name='Language', language='Test')
        self.service = TeachingService(self.project)

    def lesson(self, identifier, source, glosses):
        self.service.submit(identifier, source)
        ticket = self.service.predict(identifier)
        return self.service.correct(ticket['prediction_id'], glosses), ticket

    def test_real_workspace_teach_transfer_confirm_reopen_and_review(self):
        self.lesson('anchors', 'tal mir', ['tree', 'bird'])
        self.service.submit('probe', 'mirum')
        before = self.service.predict('probe')
        self.assertIsNone(before['words'][0]['gloss'])
        self.lesson('plural', 'talum', ['tree-PL'])
        after = self.service.predict('probe')
        self.assertEqual(after['words'][0]['gloss'], 'bird-PL')
        self.service.confirm(after['prediction_id'])
        restored = self.store.open(self.path)
        self.assertEqual(restored.prediction(before['prediction_id']), before)
        self.assertEqual(restored.model_identity(), self.project.model_identity())
        self.assertEqual(restored.history('probe'), self.project.history('probe'))
        self.assertTrue(restored.workspace.model.contextual)
        self.assertEqual(LanguageProject.open(self.path).predict('probe')[0]['gloss'], 'bird-PL')
        self.assertEqual(search(restored, 'bird-PL')[0]['id'], 'probe')
        self.assertEqual(review_queue(restored)['total_reviewable'], 0)

    def test_imported_workspace_revisions_gain_cli_history_without_migration(self):
        raw = self.project.workspace
        raw.add_corpus('seed.tsv', 'tal\ttree\n', 'tsv')
        identifier = raw.data['sentences'][0]['id']
        project = self.store.open(self.path)
        original = copy.deepcopy(project.workspace.data['annotation_history'][0])
        service = TeachingService(project)
        ticket = service.predict(identifier)
        service.correct(ticket['prediction_id'], ['bird'], replace=True, reason='correcting imported meaning')
        reopened = self.store.open(self.path)
        self.assertEqual(reopened.workspace.data['schema_version'], 1)
        self.assertEqual(reopened.workspace.data['annotation_history'][0], original)
        self.assertEqual([row['action'] for row in reopened.history(identifier)], ['workspace', 'correct'])
        self.assertEqual(reopened.history(identifier)[-1]['reason'], 'correcting imported meaning')

    def test_export_restore_carries_predictions_reasons_and_idempotency(self):
        self.service.submit('word', 'tal')
        ticket = self.service.predict('word')
        first = self.service.correct(ticket['prediction_id'], ['tree'], operation_id='retry-once')
        backup = self.directory/'backup.zip'
        self.project.export(backup)
        restored_path = self.directory/'restored.dproj'
        LanguageProject.restore(backup, restored_path)
        restored = self.store.open(restored_path)
        replay = TeachingService(restored).correct(ticket['prediction_id'], ['tree'], operation_id='retry-once')
        self.assertEqual(replay['correction'], first['correction'])
        self.assertEqual(restored.model_version, 1)
        self.assertEqual(restored.prediction(ticket['prediction_id']), ticket)
        self.assertEqual(restored.history('word'), self.project.history('word'))

    def test_stale_workspace_and_stale_annotation_guards_prevent_cross_client_loss(self):
        self.service.submit('word', 'tal')
        ticket = self.service.predict('word')
        stale_web_project = LanguageProject.open(self.path)
        self.service.correct(ticket['prediction_id'], ['tree'])
        saved = self.path.read_bytes()
        with self.assertRaises(ProjectWriteConflict):
            stale_web_project.correct('word', ['bird'], expected_revision=0)
        self.assertEqual(self.path.read_bytes(), saved)
        current = LanguageProject.open(self.path)
        before = copy.deepcopy(current.model.__dict__)
        with self.assertRaises(AnnotationRevisionConflict):
            current.correct('word', ['bird'], expected_revision=0)
        self.assertEqual(current.model.__dict__, before)
        with self.assertRaises(RevisionConflict):
            self.service.correct(ticket['prediction_id'], ['bird'], replace=True, reason='stale ticket')

    def test_cli_save_cannot_overwrite_a_newer_web_annotation(self):
        self.service.submit('word', 'tal')
        ticket = self.service.predict('word')
        web = LanguageProject.open(self.path)
        web.correct('word', ['bird'], expected_revision=0)
        saved = self.path.read_bytes()
        with self.assertRaises(ProjectConflict):
            self.service.correct(ticket['prediction_id'], ['tree'])
        self.assertEqual(self.path.read_bytes(), saved)
        self.assertEqual(self.store.open(self.path).annotation('word')['glosses'], ['bird'])

    def test_failed_combined_save_never_commits_half_a_correction(self):
        self.service.submit('word', 'tal')
        ticket = self.service.predict('word')
        saved = self.path.read_bytes()
        def partial(value, handle, **kwargs):
            handle.write('{"schema_version":')
            raise OSError('injected partial save')
        with patch('decipher.project.json.dump', side_effect=partial):
            with self.assertRaises(OSError):
                self.service.correct(ticket['prediction_id'], ['tree'], operation_id='recover-once')
        self.assertEqual(self.path.read_bytes(), saved)
        self.assertEqual([path.name for path in self.directory.iterdir()], ['language.dproj'])
        restored = self.store.open(self.path)
        self.assertEqual(restored.model_version, 0)
        self.assertIsNone(restored.annotation('word'))
        TeachingService(restored).correct(ticket['prediction_id'], ['tree'], operation_id='recover-once')
        self.assertEqual(self.store.open(self.path).model_version, 1)

    def test_contextual_setting_is_part_of_calibration_identity(self):
        first, second = GlossLearner(contextual=False), GlossLearner(contextual=True)
        example = TextExample('one', ('tal',))
        first.correct(example, ['tree'])
        second.correct(example, ['tree'])
        self.assertNotEqual(learner_identity(first), learner_identity(second))

    def test_malformed_teaching_metadata_is_rejected_before_more_answers(self):
        self.service.submit('word', 'tal')
        ticket = self.service.predict('word')
        data = json.loads(self.path.read_text(encoding='utf-8'))
        data['teaching']['predictions'][ticket['prediction_id']]['model_version'] = 99
        self.path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.store.open(self.path)

    def test_default_cli_uses_real_workspace_without_site_packages(self):
        path = self.directory/'cli.dproj'
        def cli(*arguments):
            result = subprocess.run([sys.executable, '-X', 'utf8', '-S', '-m', 'decipher.app', 'gloss', 'teach',
                                     *map(str, arguments), '--project', str(path), '--json'],
                                    capture_output=True, text=True, encoding='utf-8', check=True)
            return json.loads(result.stdout)
        cli('init', '--name', 'Real CLI', '--language', 'Test')
        cli('submit', '--id', 'word', '--text', 'tal')
        ticket = cli('predict', '--id', 'word')
        result = cli('correct', '--prediction', ticket['prediction_id'], '--glosses', 'tree')
        self.assertEqual(result['correction']['revision'], 1)
        self.assertEqual(cli('history', '--id', 'word')[0]['glosses'], ['tree'])
        self.assertEqual(LanguageProject.open(path).predict('word')[0]['gloss'], 'tree')

    def test_web_rejects_stale_review_revision_with_conflict_response(self):
        self.service.submit('word', 'tal')
        app = GlossWebApp(self.directory)
        app.project = LanguageProject.open(self.path)
        def correct(gloss):
            payload = json.dumps({'id': 'word', 'glosses': [gloss], 'expected_revision': 0}).encode()
            captured = {}
            body = b''.join(app({'REQUEST_METHOD': 'POST', 'PATH_INFO': '/api/correct', 'HTTP_HOST': '127.0.0.1:8765',
                                 'CONTENT_LENGTH': str(len(payload)), 'wsgi.input': io.BytesIO(payload)},
                                lambda status, headers: captured.update(status=status)))
            return captured['status'], json.loads(body)
        self.assertTrue(correct('tree')[0].startswith('200'))
        status, result = correct('bird')
        self.assertTrue(status.startswith('409'))
        self.assertIn('current revision 1', result['error'])
        self.assertEqual(LanguageProject.open(self.path).predict('word')[0]['gloss'], 'tree')


if __name__ == '__main__':
    unittest.main()
