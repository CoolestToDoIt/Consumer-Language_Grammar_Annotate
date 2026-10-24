"""Deadline, private scoring, memory units and frozen adoption criteria."""
import copy
import sys
import unittest

from decipher.corpus import TextExample
from decipher.gloss import GlossExample, lexical_key
from tools.evaluate_internal_edits import adoption_decision, bounded_child, peak_memory, score_pairs


def prediction(gloss, *, known=False, alternatives=()):
    return {'gloss': gloss, 'known_form': known,
            'candidates': [{'gloss': item, 'score': 1.0} for item in
                           ((gloss,) if gloss is not None else ())+tuple(alternatives)]}


def passing_records():
    reports = []
    for language in ('lezgi', 'tsez'):
        reports.append({
            'language': language, 'status': 'complete',
            'source': {'implementation_sha256': {'engine': 'fixed'}},
            'baseline': {'word_accuracy': .7, 'grounded_oov_accuracy': .2},
            'experimental': {'word_accuracy': .71, 'grounded_oov_accuracy': .22},
            'known_form_equality': {'candidate_mismatches': 0},
            'checks': {'checkpoint_full_candidates_exact': True, 'checkpoint_rules_exact': True},
            'timings': {'baseline_prediction_seconds': .2, 'experimental_prediction_seconds': .3},
            'memory': {'peak_bytes': 100*1024*1024},
            'process': {'status': 'exited', 'returncode': 0, 'timeout_seconds': 120},
        })
    return reports, {'successful': True, 'skipped': 0, 'code_unchanged_during_tests': True,
                     'implementation_sha256': {'engine': 'fixed'}}


class InternalExperimentTests(unittest.TestCase):
    def test_child_deadline_terminates_and_nonzero_exits_are_preserved(self):
        timed = bounded_child([sys.executable, '-S', '-c', 'import time; time.sleep(10)'], .1)
        self.assertEqual(timed['status'], 'timeout')
        self.assertIsNone(timed['returncode'])
        exited = bounded_child([sys.executable, '-S', '-c', 'raise SystemExit(7)'], 10)
        self.assertEqual((exited['status'], exited['returncode']), ('exited', 7))
        for invalid in (0, -1, 121, True, float('nan'), float('inf')):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                bounded_child([], invalid)

    def test_peak_memory_is_a_positive_byte_count_with_api_name(self):
        measured = peak_memory()
        self.assertIsInstance(measured['peak_bytes'], int)
        self.assertGreater(measured['peak_bytes'], 0)
        self.assertTrue(measured['api'])

    def test_private_scoring_rebuilds_transitions_and_grounded_failure_categories(self):
        gold = GlossExample(TextExample('sentence', ('known', 'new1', 'new2', 'new3', 'new4', 'new5')),
                            ('tree', 'tree-PL', 'tree-DU', 'tree-DAT', 'tree-LOC', 'unseen'))
        before = [prediction('wrong', known=True), prediction(None), prediction('tree-DU'),
                  prediction('tree'), prediction(None), prediction(None)]
        after = [prediction('wrong', known=True), prediction('tree-PL'), prediction(None),
                 prediction('tree', alternatives=('tree-DAT',)), prediction('tree'), prediction(None)]
        snapshot = copy.deepcopy((gold, before, after))
        score, changed = score_pairs([gold], [before], [after], [lexical_key('tree')])
        self.assertEqual(score['baseline']['counts']['correct'], 1)
        self.assertEqual(score['experimental']['counts']['correct'], 1)
        self.assertEqual(score['baseline']['grounded_oov_accuracy'], .25)
        self.assertEqual(score['known_form_equality'], {'words': 1, 'candidate_mismatches': 0})
        self.assertEqual(score['transitions']['baseline_correct_only'], 1)
        self.assertEqual(score['transitions']['experimental_correct_only'], 1)
        self.assertEqual(len(changed), 4)
        self.assertEqual(score['grounded_oov_failures']['experimental'], {
            'correct': 1, 'grounded_lexeme_not_recovered': 1,
            'correct_gloss_below_top1': 1, 'grammatical_output_missing': 1})
        self.assertEqual((gold, before, after), snapshot)
        with self.assertRaises(ValueError):
            score_pairs([gold], [], [after], [])
        with self.assertRaises(ValueError):
            score_pairs([gold], [before], [[{**after[0], 'known_form': False}, *after[1:]]], [])

    def test_passing_screen_still_requires_separate_default_approval(self):
        reports, tests = passing_records()
        before = copy.deepcopy((reports, tests))
        result = adoption_decision(reports, tests)
        self.assertEqual(result['decision'], 'recommend_adoption_review')
        self.assertFalse(result['default_changed'])
        self.assertEqual(result['failed_checks'], [])
        self.assertAlmostEqual(result['mean_grounded_oov_gain_pp'], 2)
        self.assertEqual((reports, tests), before)

    def test_each_frozen_gate_can_reject_default_adoption(self):
        mutations = (
            ('word_accuracy_gate', lambda r, t: r[0]['experimental'].update(word_accuracy=.69)),
            ('grounded_oov_loss_gate', lambda r, t: r[0]['experimental'].update(grounded_oov_accuracy=.19)),
            ('mean_grounded_oov_gain', lambda r, t: [row['experimental'].update(grounded_oov_accuracy=.205) for row in r]),
            ('prediction_gate', lambda r, t: r[0]['timings'].update(experimental_prediction_seconds=1)),
            ('memory_gate', lambda r, t: r[0]['memory'].update(peak_bytes=513*1024*1024)),
            ('deadline_gate', lambda r, t: r[0]['process'].update(timeout_seconds=121)),
            ('both_full_runs_complete', lambda r, t: r[0].update(status='timeout')),
            ('known_forms_exact', lambda r, t: r[0]['known_form_equality'].update(candidate_mismatches=1)),
            ('checkpoint_reconstruction', lambda r, t: r[0]['checks'].update(checkpoint_rules_exact=False)),
            ('regressions_passed', lambda r, t: t.update(skipped=1)),
            ('same_tested_implementation', lambda r, t: t.update(implementation_sha256={'engine': 'other'})),
        )
        for gate, change in mutations:
            with self.subTest(gate=gate):
                reports, tests = passing_records()
                change(reports, tests)
                result = adoption_decision(reports, tests)
                self.assertEqual(result['decision'], 'reject_default_adoption')
                self.assertIn(gate, result['failed_checks'])
                self.assertFalse(result['default_changed'])

    def test_tiny_prediction_times_use_the_frozen_absolute_allowance(self):
        reports, tests = passing_records()
        reports[0]['timings'] = {'baseline_prediction_seconds': .01, 'experimental_prediction_seconds': .2}
        self.assertEqual(adoption_decision(reports, tests)['decision'], 'recommend_adoption_review')
        reports[0]['timings']['experimental_prediction_seconds'] = .4
        self.assertIn('prediction_gate', adoption_decision(reports, tests)['failed_checks'])


if __name__ == '__main__':
    unittest.main()
