import io
import json
from pathlib import Path
import tempfile
import unittest

from decipher.gloss_web import GlossWebApp, PAGE
from decipher.project import LanguageProject

LESSONS = '\n'.join([
    'tal\ttree', 'mir\tbird', 'vel\tflower', 'kor\tdog',
    'talum\ttree-PL', 'mirum\tbird-PL', 'velum\tflower-PL',
    'talek\ttree-ERG', 'mirek\tbird-ERG', 'korek\tdog-ERG',
    'vosa\tsee-PRS', 'vosni\tsee-FUT', 'vosta\tsee-PST', 'kela\tchase-PRS', 'kelni\tchase-FUT', 'kelta\tchase-PST',
    'tal.\ttree', 'zo\tDEM',
    'korum',
])


class LanguageKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = LanguageProject.create(Path(self.tmp.name) / 'velari.dproj', 'Velari', 'und')
        self.project.add_corpus('lessons.tsv', LESSONS, 'tsv')

    def test_vocabulary_groups_forms_by_meaning(self):
        vocabulary = {row['meaning']: row for row in self.project.knowledge()['vocabulary']}
        self.assertEqual({row['form'] for row in vocabulary['tree']['forms']}, {'tal', 'talum', 'talek', 'tal.'})
        self.assertEqual(vocabulary['tree']['count'], 4)
        function_words = self.project.knowledge()['function_words']
        self.assertEqual([(row['form'], row['gloss']) for row in function_words], [('zo', 'DEM')])

    def test_endings_need_two_meanings_aligned_tags_and_no_punctuation(self):
        endings = self.project.knowledge()['endings']
        found = {(row['kind'], row['affix'], row['tag'], row['replaces_affix'], row['replaces_tag']) for row in endings}
        self.assertIn(('add', 'um', 'PL', '', ''), found)
        self.assertIn(('add', 'ek', 'ERG', '', ''), found)
        swaps = [row for row in endings if row['kind'] == 'swap']
        self.assertTrue(any({row['replaces_tag'], row['tag']} == {'PRS', 'FUT'} for row in swaps))
        self.assertFalse(any(row['tag'] in ('ST', 'RS') or row['replaces_tag'] in ('ST', 'RS') for row in endings))
        self.assertFalse(any('.' in row['affix'] for row in endings))
        plural = next(row for row in endings if row['affix'] == 'um')
        self.assertEqual(plural['meanings'], 3)
        self.assertIn({'base': 'tal', 'base_gloss': 'tree', 'form': 'talum', 'gloss': 'tree-PL'}, plural['examples'])

    def test_language_details_update_without_changing_identity(self):
        path = self.project.path
        self.project.update_language(name='Velari (demo)', language_id='', description=' Invented. ')
        reopened = LanguageProject.open(path)
        self.assertEqual(reopened.summary()['name'], 'Velari (demo)')
        self.assertEqual(reopened.summary()['language_id'], 'und')
        self.assertEqual(reopened.summary()['description'], 'Invented.')
        self.assertEqual(reopened.summary()['project_id'], 'velari')
        with self.assertRaises(ValueError):
            self.project.update_language(description='x' * 5000)

    def test_queue_includes_saved_glosses_for_reviewed_sentences(self):
        queue = self.project.queue()
        self.assertIsNone(next(row for row in queue if row['tokens'] == ['korum'])['glosses'])
        self.assertEqual(next(row for row in queue if row['tokens'] == ['talum'])['glosses'], ['tree-PL'])


class LanguageApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = GlossWebApp(self.tmp.name)

    def call(self, path, value=None, project=None):
        body = json.dumps(value).encode() if value is not None else b''
        env = {'REQUEST_METHOD': 'POST' if value is not None else 'GET', 'PATH_INFO': path, 'QUERY_STRING': '',
               'HTTP_HOST': '127.0.0.1:8765', 'CONTENT_TYPE': 'application/json',
               'CONTENT_LENGTH': str(len(body)), 'wsgi.input': io.BytesIO(body)}
        if project:
            env['HTTP_X_PROJECT_ID'] = project
        response = {}
        raw = b''.join(self.app(env, lambda status, headers: response.update(status=int(status[:3]))))
        return response['status'], json.loads(raw)

    def test_create_with_optional_code_and_description_then_edit_and_list(self):
        status, created = self.call('/api/projects', {'name': 'Velari', 'language_id': ' ', 'description': 'Invented'})
        self.assertEqual(status, 201)
        self.assertEqual((created['language_id'], created['description'], created['sentences']), ('und', 'Invented', 0))
        project = created['project_id']
        self.call('/api/import', {'name': 'lessons.tsv', 'content': LESSONS}, project)
        status, knowledge = self.call('/api/knowledge', project=project)
        self.assertEqual(status, 200)
        self.assertEqual(knowledge['stats']['reviewed'], 18)
        self.assertTrue(knowledge['endings'])
        status, summary = self.call('/api/language', {'language_id': 'xvl'}, project)
        self.assertEqual((status, summary['language_id']), (200, 'xvl'))
        self.assertEqual(self.call('/api/language', {'project_id': 'other'}, project)[0], 400)
        _, listed = self.call('/api/projects')
        self.assertEqual(listed[0]['sentences'], 19)
        self.assertEqual(listed[0]['reviewed'], 18)

    def test_page_is_served_from_the_packaged_html(self):
        self.assertIn('Pick up where you left off', PAGE)
        self.assertIn('On this computer', PAGE)
        self.assertNotIn('innerHTML', PAGE)


if __name__ == '__main__':
    unittest.main()
