import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from decipher.gloss_web import GlossWebApp
from decipher.project import LanguageProject, ProjectWriteConflict


class CommercialWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = GlossWebApp(self.tmp.name)

    def call(self, path, value=None, project=None, **headers):
        body = json.dumps(value).encode() if value is not None else b''
        route, _, query = path.partition('?')
        env = {'REQUEST_METHOD': 'POST' if value is not None else 'GET', 'PATH_INFO': route,
               'QUERY_STRING': query, 'HTTP_HOST': '127.0.0.1:8765', 'CONTENT_TYPE': 'application/json',
               'CONTENT_LENGTH': str(len(body)), 'wsgi.input': io.BytesIO(body), **headers}
        if project:
            env['HTTP_X_PROJECT_ID'] = project
        response = {}
        raw = b''.join(self.app(env, lambda status, fields: response.update(status=int(status[:3]), headers=dict(fields))))
        return response['status'], raw

    def create(self, name):
        status, raw = self.call('/api/projects', {'name': name, 'language_id': 'invented'})
        self.assertEqual(status, 201)
        return json.loads(raw)['project_id']

    def test_demo_governance_export_restore_on_clean_workspace_and_delete(self):
        status, raw = self.call('/api/demo', {})
        self.assertEqual(status, 201)
        project = json.loads(raw)['project_id']
        policy = dict(owner='Team', license='Private pilot', consent='Approved sample', provenance='Invented', retention='30 days', conventions='Custom tags')
        self.assertEqual(self.call('/api/governance', policy, project)[0], 200)
        status, raw = self.call('/api/annotations', project=project)
        rows = [json.loads(line) for line in raw.splitlines()]
        self.assertEqual(len(rows), 7)
        self.assertIsNone(rows[-1]['glosses'])
        self.assertFalse(rows[-1]['reviewed'])
        self.assertIn(b'tal\ttree\n', self.call('/api/annotations?format=tsv', project=project)[1])
        _, backup = self.call('/api/export', project=project)
        with tempfile.TemporaryDirectory() as clean:
            self.app = GlossWebApp(clean)
            status, raw = self.call('/api/restore', {'name': 'Restored', 'archive': base64.b64encode(backup).decode()})
            self.assertEqual(status, 201)
            restored = json.loads(raw)['project_id']
            _, summary = self.call('/api/project', project=restored)
            self.assertEqual(json.loads(summary)['governance'], policy)
            self.assertEqual(len(json.loads(self.call('/api/history', project=restored)[1])), 6)
            self.assertEqual(self.call('/api/delete', {'name': 'wrong'}, restored)[0], 400)
            self.assertEqual(self.call('/api/delete', {'name': 'Restored'}, restored)[0], 200)
            self.assertFalse(list(Path(clean).glob('*.dproj')))

    def test_browser_projects_stay_separate_and_stale_reviews_are_rejected(self):
        first, second = self.create('First'), self.create('Second')
        self.call('/api/import', {'name': 'input.txt', 'content': 'tal'}, first)
        self.call('/api/open', {'project_id': second})
        _, raw = self.call('/api/queue', project=first)
        sentence = json.loads(raw)[0]
        self.assertEqual(self.call('/api/correct', {'id': sentence['id'], 'glosses': ['tree'], 'expected_revision': 0}, first)[0], 200)
        self.assertEqual(self.call('/api/correct', {'id': sentence['id'], 'glosses': ['bird'], 'expected_revision': 0}, first)[0], 409)
        self.assertEqual(json.loads(self.call('/api/queue', project=second)[1]), [])
        self.assertEqual(self.call('/api/project', project='missing')[0], 400)

    def test_cross_origin_host_spoof_and_form_posts_are_rejected(self):
        for headers in ({'HTTP_HOST': '127.0.0.1:8765.evil.test'}, {'HTTP_ORIGIN': 'https://evil.test'}, {'HTTP_SEC_FETCH_SITE': 'cross-site'}):
            self.assertEqual(self.call('/api/projects', **headers)[0], 403)
        self.assertEqual(self.call('/api/projects', {}, CONTENT_TYPE='text/plain')[0], 415)

    def test_invalid_import_does_not_save_partial_data(self):
        project = self.create('Invalid')
        self.assertEqual(self.call('/api/import', {'name': 'bad.tsv', 'content': 'tal\ttree\nmir vel\tbird'}, project)[0], 400)
        self.assertEqual(json.loads(self.call('/api/queue', project=project)[1]), [])
        self.assertEqual(self.call('/api/import', {'name': 'empty.igt', 'content': '# no source tiers', 'format': 'sigmorphon'}, project)[0], 400)
        self.assertEqual(self.call('/api/import', {'name': 'bom.txt', 'content': '\ufefftal'}, project)[0], 201)
        self.assertEqual(json.loads(self.call('/api/queue', project=project)[1])[0]['tokens'], ['tal'])

    def test_failed_atomic_write_preserves_saved_project_and_releases_lock(self):
        project_id = self.create('Atomic')
        project = LanguageProject.open(Path(self.tmp.name) / f'{project_id}.dproj')
        original = project.path.read_bytes()
        project.data['name'] = 'Changed'
        with patch('decipher.project.os.fsync', side_effect=OSError('Simulated interrupted write')):
            with self.assertRaises(OSError):
                project.save()
        self.assertEqual(project.path.read_bytes(), original)
        self.assertFalse(project.path.with_name(project.path.name + '.lock').exists())
        project.save()
        self.assertEqual(LanguageProject.open(project.path).data['name'], 'Changed')

    def test_disk_conflict_preserves_newer_annotations(self):
        identifier = self.create('Conflict')
        path = Path(self.tmp.name) / f'{identifier}.dproj'
        first, stale = LanguageProject.open(path), LanguageProject.open(path)
        first.add_corpus('one.tsv', 'tal\ttree', 'tsv')
        stale.data['name'] = 'Stale'
        with self.assertRaises(ProjectWriteConflict):
            stale.save()
        self.assertEqual(LanguageProject.open(path).annotation_count, 1)

    def test_future_or_malformed_backup_is_rejected_before_save(self):
        identifier = self.create('Schema')
        path = Path(self.tmp.name) / f'{identifier}.dproj'
        data = json.loads(path.read_text())
        for change in ({'schema_version': 999}, {'governance': []}):
            with self.assertRaises(ValueError):
                LanguageProject(path, {**data, **change})


if __name__ == '__main__':
    unittest.main()
