import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from decipher.corpus import TextExample
from decipher.gloss import GlossExample, GlossLearner
from decipher.gloss_web import GlossWebApp
from decipher.project import LanguageProject, list_projects


class LanguageProjectTests(unittest.TestCase):
    def test_projects_reopen_with_independent_annotations_and_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            first = LanguageProject.create(Path(directory) / 'lezgi.dproj', 'Lezgi', 'lez')
            second = LanguageProject.create(Path(directory) / 'tsez.dproj', 'Tsez', 'ddo', {'mode': 'memory', 'contextual': False})
            first.add_corpus('lesson.tsv', 'tal river\tshore river\nriver\triver\n', 'tsv')
            sentence = first.data['sentences'][0]
            first.correct(sentence['id'], ('bank', 'river'))
            first.correct(sentence['id'], ('shore', 'river'))

            reopened = LanguageProject.open(first.path)
            other = LanguageProject.open(second.path)
            self.assertEqual(reopened.data, first.data)
            self.assertEqual(reopened.model.__dict__, first.model.__dict__)
            self.assertEqual(reopened.model.predict(TextExample(sentence['id'], tuple(sentence['tokens']))),
                             first.model.predict(TextExample(sentence['id'], tuple(sentence['tokens']))))
            self.assertEqual(reopened.data['annotation_history'][-1]['revision'], 3)
            self.assertEqual(other.data['language_id'], 'ddo')
            self.assertEqual(other.model.contextual, False)
            self.assertEqual(len(list_projects(directory)), 2)

    def test_import_prediction_correction_backup_and_restore_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'original.dproj'
            project = LanguageProject.create(path, 'Lezgi', 'lez')
            count = project.add_corpus('lessons.tsv', 'tal\tshore\nmir\tbird\nunseenum\n', 'tsv')
            self.assertEqual(count, 3)
            queue = project.queue()
            self.assertEqual([item['tokens'] for item in queue], [['unseenum'], ['tal'], ['mir']])
            self.assertFalse(queue[0]['annotated'])
            self.assertTrue(queue[1]['annotated'])
            self.assertFalse(queue[0]['predictions'][0]['known_form'])
            self.assertTrue(queue[0]['predictions'][0]['provisional'])
            self.assertTrue(queue[0]['predictions'][0]['gloss'])
            self.assertTrue(project.correct(queue[0]['id'], ('unknown',)))
            self.assertFalse(project.correct(queue[0]['id'], ('unknown',)))
            with self.assertRaisesRegex(ValueError, 'array'):
                project.correct(queue[0]['id'], 'single')
            backup = Path(directory) / 'backup.zip'
            project.export(backup)
            restored = LanguageProject.restore(backup, Path(directory) / 'restored.dproj')
            self.assertEqual(restored.data['annotation_history'], project.data['annotation_history'])
            self.assertEqual(restored.data['corpora'], project.data['corpora'])
            self.assertEqual(restored.queue(), project.queue())

    def test_sig_morphon_source_only_import_and_invalid_alignment(self):
        with tempfile.TemporaryDirectory() as directory:
            project = LanguageProject.create(Path(directory) / 'project.dproj', 'Tsez', 'ddo')
            project.add_corpus('sample', '\\t tal mir\n\\g tree bird\n\n\\t vel\n', 'sigmorphon')
            self.assertEqual(len(project.data['sentences']), 2)
            self.assertEqual(project.model.lexicon['tal']['tree'], 1)
            with self.assertRaisesRegex(ValueError, 'aligned'):
                project.add_corpus('bad.tsv', 'tal mir\ttree\n', 'tsv')
            unsafe = {**project.data, 'project_id': '../outside'}
            with self.assertRaisesRegex(ValueError, 'path separators'):
                LanguageProject(project.path, unsafe)
            repeated = dict(project.data)
            repeated['annotation_history'] = [
                *project.data['annotation_history'],
                {**project.data['annotation_history'][0], 'revision': 2},
            ]
            repeated['checkpoint'] = {'model_version': 2, 'annotation_count': 1}
            with self.assertRaisesRegex(ValueError, 'unchanged revision'):
                LanguageProject(project.path, repeated)

    def test_contextual_benchmark_improves_disambiguation_without_nonambiguity_regression(self):
        training = [
            ('shore-context', ('tal', 'river', 'flows'), ('shore', 'river', 'flow')),
            ('bank-context', ('tal', 'money', 'flows'), ('bank', 'money', 'flow')),
        ]
        baseline = GlossLearner().fit(
            GlossExample(TextExample(identifier, tokens), glosses)
            for identifier, tokens, glosses in training
        )
        contextual = GlossLearner(contextual=True).fit(
            GlossExample(TextExample(identifier, tokens), glosses)
            for identifier, tokens, glosses in training
        )
        benchmark = [
            (('today', 'tal', 'river', 'flows'), 'shore'),
            (('today', 'tal', 'money', 'flows'), 'bank'),
        ]
        baseline_correct = 0
        contextual_correct = 0
        for index, (tokens, expected) in enumerate(benchmark):
            example = TextExample(f'heldout-{index}', tokens)
            baseline_prediction = baseline.predict(example)[1]
            contextual_prediction = contextual.predict(example)[1]
            baseline_correct += baseline_prediction['gloss'] == expected
            contextual_correct += contextual_prediction['gloss'] == expected
            self.assertTrue(contextual_prediction['context_used'])
        self.assertEqual(baseline_correct, 1)
        self.assertEqual(contextual_correct, 2)
        unaffected = TextExample('unambiguous', ('river', 'flows'))
        self.assertEqual(contextual.predict(unaffected)[0]['gloss'], baseline.predict(unaffected)[0]['gloss'])
        many_senses = GlossLearner(contextual=True).fit(
            GlossExample(TextExample(f'sense-{index}', ('tal', f'situation-{index}')),
                        (f'sense-{index}', f'situation-{index}'))
            for index in range(6)
        )
        sixth_sense = many_senses.predict(TextExample('heldout-sixth', ('tal', 'situation-5')))[0]
        self.assertEqual(sixth_sense['gloss'], 'sense-5')
        self.assertEqual(len(sixth_sense['candidates']), 5)
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / 'context.gz'
            contextual.save(checkpoint)
            self.assertEqual(GlossLearner.load(checkpoint).predict(TextExample('heldout', benchmark[0][0])),
                             contextual.predict(TextExample('heldout', benchmark[0][0])))


class GlossWebTests(unittest.TestCase):
    def test_local_web_api_runs_import_teach_export_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            app = GlossWebApp(directory)

            def call(path, method='GET', value=None):
                raw = json.dumps(value).encode() if value is not None else b''
                captured = {}

                def start_response(status, headers):
                    captured['status'] = status
                    captured['headers'] = dict(headers)

                result = b''.join(app({
                    'REQUEST_METHOD': method,
                    'PATH_INFO': path,
                    'HTTP_HOST': '127.0.0.1:8765', 'CONTENT_TYPE': 'application/json',
                    'CONTENT_LENGTH': str(len(raw)),
                    'wsgi.input': io.BytesIO(raw),
                }, start_response))
                return captured, result

            response, raw = call('/api/projects', 'POST', {'name': 'Lezgi', 'language_id': 'lez'})
            self.assertTrue(response['status'].startswith('201'))
            identifier = json.loads(raw)['project_id']
            call('/api/open', 'POST', {'project_id': identifier})
            _, preview_raw = call('/api/import/preview', 'POST', {
                'name': 'lesson.tsv', 'format': 'tsv', 'content': 'tal\tshore\nunseen\n',
            })
            preview = json.loads(preview_raw)
            self.assertEqual(preview['sentence_count'], 2)
            self.assertEqual(preview['annotated_count'], 1)
            self.assertEqual(preview['needs_review_count'], 1)
            self.assertEqual(call('/api/queue')[1], b'[]')
            call('/api/import', 'POST', {'name': 'lesson.tsv', 'format': 'tsv', 'content': 'tal\tshore\nunseen\n'})
            _, raw = call('/api/queue')
            sentence = json.loads(raw)[0]
            self.assertEqual(sentence['tokens'], ['unseen'])
            self.assertTrue(sentence['predictions'][0]['provisional'])
            call('/api/correct', 'POST', {'id': sentence['id'], 'glosses': ['tree']})
            response, archive = call('/api/export')
            self.assertEqual(response['headers']['Content-Type'], 'application/zip')
            self.assertTrue(zipfile.is_zipfile(io.BytesIO(archive)))
            response, raw = call('/api/restore', 'POST', {
                'name': 'Restored Lezgi',
                'archive': base64.b64encode(archive).decode('ascii'),
            })
            self.assertTrue(response['status'].startswith('201'))
            restored_id = json.loads(raw)['project_id']
            app.project = None
            call('/api/open', 'POST', {'project_id': restored_id})
            _, raw = call('/api/queue')
            reopened = {item['id']: item for item in json.loads(raw)}
            self.assertEqual(reopened[sentence['id']]['predictions'][0]['gloss'], 'tree')

    def test_api_rejects_nonlocal_hosts(self):
        app = GlossWebApp('/tmp/nonexistent-decipher-workspace')
        captured = {}
        response = b''.join(app({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/api/projects', 'HTTP_HOST': 'attacker.example',
                                 'CONTENT_LENGTH': '0', 'wsgi.input': io.BytesIO()}, lambda status, headers: captured.update(status=status)))
        self.assertTrue(captured['status'].startswith('403'))
        self.assertEqual(json.loads(response)['error'], 'Local requests only')


if __name__ == '__main__':
    unittest.main()
