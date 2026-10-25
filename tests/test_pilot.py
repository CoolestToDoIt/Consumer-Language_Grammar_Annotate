import io
import json
from pathlib import Path
import tempfile
import unittest

from decipher.gloss_web import GlossWebApp
from decipher.project import LanguageProject

# tal is glossed tree four times and wood once (a likely slip). zo is split
# evenly between two glosses, and ka between two common glosses plus a rare one:
# real ambiguity, so neither is flagged.
SLIP = '\n'.join(['tal\ttree'] * 4 + ['tal\twood'] + ['zo\tDEM'] * 3 + ['zo\tthat'] * 3
                 + ['ka\tone'] * 5 + ['ka\ttwo'] * 4 + ['ka\tthree'])


class PilotMeasureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = LanguageProject.create(Path(self.tmp.name) / 'velari.dproj', 'Velari', 'und')

    def test_summary_names_recorded_policy_fields_only(self):
        self.assertEqual(self.project.summary()['policy_recorded'], [])
        self.project.data['governance'] = {'owner': 'Community archive', 'license': '', 'consent': ' Signed 2026 ',
                                           'provenance': '', 'retention': '', 'conventions': ''}
        self.project.save()
        self.assertEqual(LanguageProject.open(self.project.path).summary()['policy_recorded'], ['owner', 'consent'])

    def test_revisions_count_glosses_changed_after_first_save(self):
        self.project.add_corpus('a.tsv', 'tal mir\ttree bird\nvel\tflower', 'tsv')
        first = next(row for row in self.project.queue() if row['tokens'] == ['tal', 'mir'])
        self.project.correct(first['id'], ['tree', 'crow'])
        self.project.correct(first['id'], ['wood', 'bird'])
        self.assertEqual(self.project.performance()['revisions'], {'sentences': 1, 'glosses': 3})

    def test_rare_variant_is_flagged_and_balanced_ambiguity_is_not(self):
        self.project.add_corpus('a.tsv', SLIP, 'tsv')
        checks = self.project.unusual_glosses()
        self.assertEqual((checks['count'], checks['kept']), (1, 0))
        item = checks['items'][0]
        self.assertEqual((item['token'], item['gloss'], item['usual'], item['usual_count']), ('tal', 'wood', 'tree', 4))

    def test_kept_gloss_is_not_flagged_again_and_survives_reopening(self):
        self.project.add_corpus('a.tsv', SLIP, 'tsv')
        item = self.project.unusual_glosses()['items'][0]
        with self.assertRaises(ValueError):
            self.project.keep_gloss(item['id'], item['index'], 'tree')
        self.project.keep_gloss(item['id'], item['index'], item['gloss'])
        reopened = LanguageProject.open(self.project.path)
        self.assertEqual((reopened.unusual_glosses()['count'], reopened.unusual_glosses()['kept']), (0, 1))
        # Fixing the gloss instead clears the flag without a keep.
        reopened.correct(item['id'], ['tree'])
        self.assertEqual(reopened.unusual_glosses()['kept'], 0)

    def test_malformed_kept_list_is_rejected(self):
        self.project.data['kept_glosses'] = [[['not-an-id'], 0, 'x']]
        with self.assertRaises(ValueError):
            self.project.save()


class PilotApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        LanguageProject.create(Path(self.tmp.name) / 'velari.dproj', 'Velari', 'und').add_corpus('a.tsv', SLIP, 'tsv')
        self.app = GlossWebApp(self.tmp.name)

    def call(self, path, value=None):
        body = json.dumps(value).encode() if value is not None else b''
        env = {'REQUEST_METHOD': 'POST' if value is not None else 'GET', 'PATH_INFO': path, 'QUERY_STRING': '',
               'HTTP_HOST': '127.0.0.1:8765', 'CONTENT_TYPE': 'application/json', 'HTTP_X_PROJECT_ID': 'velari',
               'CONTENT_LENGTH': str(len(body)), 'wsgi.input': io.BytesIO(body)}
        response = {}
        raw = b''.join(self.app(env, lambda status, headers: response.update(status=int(status[:3]))))
        return response['status'], json.loads(raw)

    def test_checks_keep_and_performance_report_counts(self):
        status, checks = self.call('/api/checks')
        self.assertEqual((status, checks['count']), (200, 1))
        item = checks['items'][0]
        status, after = self.call('/api/checks/keep', {'id': item['id'], 'index': item['index'], 'gloss': item['gloss']})
        self.assertEqual((status, after['count'], after['kept']), (200, 0, 1))
        self.assertEqual(self.call('/api/checks/keep', {'id': item['id'], 'index': 'x', 'gloss': item['gloss']})[0], 400)
        status, rows = self.call('/api/performance')
        self.assertEqual(rows[0]['unusual'], {'count': 0, 'kept': 1})
        self.assertEqual(rows[0]['policy_recorded'], [])
        self.assertEqual(rows[0]['performance']['revisions'], {'sentences': 0, 'glosses': 0})


if __name__ == '__main__':
    unittest.main()
