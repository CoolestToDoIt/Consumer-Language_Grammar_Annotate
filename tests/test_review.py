"""Review ordering, search, ambiguity conflicts and read-only behavior."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from decipher.review import annotation_conflicts, review_queue, search
from decipher.teaching import TeachingService
from decipher.teaching_fixture import FixtureProjectStore


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.path = self.directory/'review.fixture.json'
        self.store = FixtureProjectStore()
        self.project = self.store.create(self.path, name='Review', language='Test')
        self.service = TeachingService(self.project)

    def teach(self, identifier, text, glosses):
        self.service.submit(identifier, text)
        ticket = self.service.predict(identifier)
        self.service.correct(ticket['prediction_id'], glosses)

    def test_unknown_first_stable_ties_and_reviewed_filter(self):
        self.teach('anchors', 'tal mir', ['tree', 'bird'])
        self.service.submit('known-word', 'tal')
        self.service.submit('unknown-first', 'zop')
        self.service.submit('unknown-second', 'vel')
        result = review_queue(self.project)
        self.assertEqual([row['id'] for row in result['items']], ['unknown-first', 'unknown-second', 'known-word'])
        self.assertEqual(result['calibration_status'], 'unavailable')
        self.assertTrue(all(row['estimated_word_error_rate'] is None for row in result['items']))
        self.assertTrue(all(not row['raw_margin_is_probability'] for row in result['items']))
        self.assertEqual(review_queue(self.project, limit=1)['items'][0]['id'], 'unknown-first')
        self.assertEqual(review_queue(self.project, include_reviewed=True)['total_reviewable'], 4)

    def test_source_conflicts_are_visible_and_not_silently_merged(self):
        self.teach('one', 'tal', ['tree'])
        self.teach('two', 'tal', ['bird'])
        self.service.submit('unreviewed', 'mir')
        conflicts = annotation_conflicts(self.project)
        self.assertEqual(len(conflicts), 1)
        result = review_queue(self.project)
        self.assertEqual([row['id'] for row in result['items'][:2]], ['one', 'two'])
        self.assertTrue(all(row['source_conflict'] for row in result['items'][:2]))
        self.assertEqual(self.project.annotation('one')['glosses'], ['tree'])
        self.assertEqual(self.project.annotation('two')['glosses'], ['bird'])
        ticket = self.service.predict('one')
        self.service.correct(ticket['prediction_id'], ['bird'], replace=True, reason='reviewed duplicate-source inconsistency')
        self.assertEqual(annotation_conflicts(self.project), [])

    def test_unicode_search_and_optional_historical_annotations(self):
        self.teach('drink', 'cafe\u0301', ['coffee'])
        self.assertEqual(search(self.project, 'CAF\u00c9')[0]['id'], 'drink')
        ticket = self.service.predict('drink')
        self.service.correct(ticket['prediction_id'], ['tea'], replace=True, reason='revised meaning')
        self.assertEqual(search(self.project, 'coffee'), [])
        historical = search(self.project, 'COFFEE', include_history=True)
        self.assertEqual(historical[0]['matched_fields'], ['history'])
        self.assertEqual(search(self.project, 'tea')[0]['annotation']['revision'], 2)

    def test_review_search_and_conflict_detection_do_not_mutate_any_project_state(self):
        self.teach('anchor', 'tal', ['tree'])
        self.service.submit('new', 'talum')
        before = copy.deepcopy(self.project._state())
        learned = copy.deepcopy(self.project.learner.__dict__)
        saved = self.path.read_bytes()
        review_queue(self.project, include_reviewed=True)
        search(self.project, 'tree', include_history=True)
        annotation_conflicts(self.project)
        self.assertEqual(self.project._state(), before)
        self.assertEqual(self.project.learner.__dict__, learned)
        self.assertEqual(self.path.read_bytes(), saved)

    def test_invalid_review_and_search_options_are_explicit_errors(self):
        for limit in (0, -1, True, 1001, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                review_queue(self.project, limit=limit)
        for query in ('', '   ', None, []):
            with self.subTest(query=query), self.assertRaises(ValueError):
                search(self.project, query)

    def test_review_and_search_cli_without_site_packages(self):
        self.teach('anchor', 'tal', ['tree'])
        self.service.submit('unknown', 'mirum')
        base = [sys.executable, '-X', 'utf8', '-S', '-m', 'decipher.app', 'gloss', 'teach']
        def cli(*arguments):
            result = subprocess.run(base+list(arguments)+['--project', str(self.path), '--backend', 'fixture', '--json'],
                                    capture_output=True, text=True, encoding='utf-8', check=True)
            return json.loads(result.stdout)
        self.assertEqual(cli('review')['items'][0]['id'], 'unknown')
        self.assertEqual(cli('search', '--query', 'tree')[0]['id'], 'anchor')

    def test_calibration_cli_saves_evidence_and_review_invalidates_after_teaching(self):
        self.service.submit('unknown', 'unseen')
        fit, validation, artifact = self.directory/'fit', self.directory/'validation', self.directory/'calibration.json'
        for path, role in ((fit, 'fit'), (validation, 'validation')):
            path.write_text(''.join(f'\\t {role}-source-{index}\n\\g concept\n\n' for index in range(100)), encoding='utf-8')
        base = [sys.executable, '-X', 'utf8', '-S', '-m', 'decipher.app', 'gloss', 'teach']
        def cli(*arguments):
            completed = subprocess.run(base+list(map(str, arguments))+['--project', str(self.path), '--backend', 'fixture', '--json'],
                                       capture_output=True, text=True, encoding='utf-8', check=True)
            return json.loads(completed.stdout)
        result = cli('calibrate', '--fit', fit, '--validation', validation, '--output', artifact)
        self.assertEqual(result['status'], 'validated')
        self.assertEqual(cli('review', '--calibration', artifact)['calibration_status'], 'validated')
        ticket = self.service.predict('unknown')
        self.service.correct(ticket['prediction_id'], ['concept'])
        result = cli('review', '--include-reviewed', '--calibration', artifact)
        self.assertEqual(result['calibration_status'], 'stale')
        self.assertIsNone(result['items'][0]['estimated_word_error_rate'])


if __name__ == '__main__':
    unittest.main()
