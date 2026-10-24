"""Frozen calibration, held-out gates, leakage prevention and invalidation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from decipher.corpus import TextExample
from decipher.gloss import GlossExample
from decipher.gloss_checkpoint import digest, encoded
from decipher.review import review_queue
from decipher.review_calibration import Calibration, DEFAULTS, build_calibration, probability_metrics
from decipher.teaching import TeachingService
from decipher.teaching_fixture import FixtureProjectStore


def record(identifier, word, target):
    return GlossExample(TextExample(identifier, (word,)), (target,))


def labeled(prefix):
    result = [record(f'{prefix}-u-{i}', f'u-{prefix}-{i}', 'unknown-concept') for i in range(40)]
    result += [record(f'{prefix}-k-{i}', f'k-{prefix}-{i}', 'known' if i < 72 else 'other') for i in range(80)]
    result += [record(f'{prefix}-r-{i}', f'r-{prefix}-{i}', 'root-PL' if i < 32 else 'root-DU') for i in range(80)]
    return result


class FrozenPredictor:
    def __init__(self):
        self.identity = 'fixed-test-model'

    def model_identity(self):
        return self.identity

    def training_sources(self):
        return (('training-only',),)

    def predict(self, example):
        if not isinstance(example, TextExample) or set(example.__dict__) != {'id', 'tokens'}:
            raise AssertionError('Answer-bearing input reached prediction')
        predictions = []
        for token in example.tokens:
            if token.startswith('k-'):
                candidates = [{'gloss': 'known', 'score': .9, 'kind': 'lexical'}]
                known = True
            elif token.startswith('r-'):
                candidates = [{'gloss': 'root-PL', 'score': 7.5, 'kind': 'rule'},
                              {'gloss': 'root-DU', 'score': 2.5, 'kind': 'rule'}]
                known = False
            elif token.startswith('new-kind-'):
                candidates = [{'gloss': 'novel', 'score': 800, 'kind': 'new-kind'}]
                known = False
            else:
                candidates, known = [], False
            predictions.append({'gloss': candidates[0]['gloss'] if candidates else None,
                                'known_form': known, 'candidates': candidates})
        return predictions


class CalibrationTests(unittest.TestCase):
    def test_probability_metrics_have_known_denominators_and_reliability_bins(self):
        result = probability_metrics([0, .5, 1], [0, 1, 0])
        self.assertAlmostEqual(result['brier'], 1.25/3)
        self.assertAlmostEqual(result['ece'], .5)
        self.assertEqual(sum(row['count'] for row in result['reliability_bins']), 3)
        self.assertIsNone(probability_metrics([], [])['ece'])
        for values in ([float('nan')], [1.1], [-.1], [True]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                probability_metrics(values, [1])

    def test_held_out_fit_validates_and_rule_scores_are_not_percentages(self):
        predictor = FrozenPredictor()
        calibration = build_calibration(predictor, labeled('fit'), labeled('validation'))
        self.assertEqual(calibration.status(predictor.model_identity()), 'validated')
        prediction = predictor.predict(TextExample('public', ('r-probe',)))[0]
        estimate = calibration.estimate(prediction, predictor.model_identity())
        self.assertAlmostEqual(estimate['estimated_accuracy'], .4, delta=.02)
        self.assertEqual(prediction['candidates'][0]['score'], 7.5)
        self.assertEqual(calibration.manifest['fit']['word_labels'], 200)
        self.assertEqual(calibration.manifest['validation']['word_labels'], 200)
        self.assertEqual(calibration.manifest['learner_training_labels_added'], 0)
        self.assertLess(calibration.validation['estimated']['brier'], calibration.validation['constant_fit_prior']['brier'])

    def test_too_little_data_failed_validation_and_unseen_strata_disable_estimates(self):
        predictor = FrozenPredictor()
        short = build_calibration(predictor, labeled('fit')[:2], labeled('validation')[:2])
        self.assertEqual(short.status(predictor.model_identity()), 'insufficient_data')
        self.assertIsNone(short.estimate(predictor.predict(TextExample('x', ('u-x',)))[0], predictor.model_identity()))
        fit = [record(f'f{i}', f'k-fit-{i}', 'known') for i in range(100)]
        validation = [record(f'v{i}', f'k-val-{i}', 'wrong') for i in range(100)]
        failed = build_calibration(predictor, fit, validation)
        self.assertEqual(failed.status(predictor.model_identity()), 'validation_failed')
        self.assertIsNone(failed.estimate(predictor.predict(TextExample('x', ('k-x',)))[0], predictor.model_identity()))
        unsupported = build_calibration(predictor, labeled('fit'),
                         [record(f'v{i}', f'new-kind-{i}', 'novel') for i in range(200)])
        self.assertEqual(unsupported.validation['coverage'], 0)
        self.assertNotEqual(unsupported.status(predictor.model_identity()), 'validated')

    def test_disjoint_sources_ids_training_exclusion_and_all_label_policy_are_required(self):
        predictor = FrozenPredictor()
        first, second = labeled('fit'), labeled('validation')
        invalid = [(first+[first[0]], second), (first, second+[first[0]]),
                   (first, [record(first[0].example.id, 'different', 'target')]),
                   (first+[record('leak', 'training-only', 'hidden')], second),
                   ([record('a', 'caf\u00e9', 'coffee'), record('b', 'cafe\u0301', 'coffee')], second)]
        for fit, validation in invalid:
            with self.subTest(size=len(fit)), self.assertRaises(ValueError):
                build_calibration(predictor, fit, validation)
        with self.assertRaisesRegex(ValueError, 'correction-only'):
            build_calibration(predictor, first, second, label_policy='corrections')

    def test_model_change_during_calibration_is_rejected(self):
        predictor = FrozenPredictor()
        original = predictor.predict
        def changing(example):
            result = original(example)
            predictor.identity = 'changed-model'
            return result
        with patch.object(predictor, 'predict', side_effect=changing):
            with self.assertRaisesRegex(ValueError, 'changed during calibration'):
                build_calibration(predictor, labeled('fit'), labeled('validation'))

    def test_save_load_integrity_and_stale_identity(self):
        predictor = FrozenPredictor()
        calibration = build_calibration(predictor, labeled('fit'), labeled('validation'))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'calibration.json'
            calibration.save(path)
            restored = Calibration.load(path)
            self.assertEqual(encoded(restored.state()), encoded(calibration.state()))
            self.assertEqual(restored.status('different-model'), 'stale')
            self.assertIsNone(restored.estimate(predictor.predict(TextExample('x', ('k-x',)))[0], 'different-model'))
            with self.assertRaises(ValueError):
                calibration.save(path)
            state = json.loads(path.read_text(encoding='utf-8'))
            state['calibration']['fit_words'] += 1
            path.write_text(json.dumps(state), encoding='utf-8')
            with self.assertRaises(ValueError):
                Calibration.load(path)

    def test_inconsistent_validation_artifacts_are_rejected_even_with_a_new_checksum(self):
        calibration = build_calibration(FrozenPredictor(), labeled('fit'), labeled('validation'))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'calibration.json'
            for change in ({'coverage': float('nan')}, {'scored_words': 999}, {'coverage': .1}, {'words': True}):
                with self.subTest(change=change):
                    state = calibration.state()
                    state['validation'] = {**state['validation'], **change}
                    # NaN is deliberately encoded by ordinary json, then rejected at load.
                    payload = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
                    path.write_text(json.dumps({'schema_version': 1, 'sha256': digest(payload), 'calibration': state}), encoding='utf-8')
                    with self.assertRaises(ValueError):
                        Calibration.load(path)

    def test_actual_project_calibration_is_read_only_and_teaching_invalidates_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = FixtureProjectStore().create(Path(tmp)/'fixture.json', name='Frozen', language='Test')
            service = TeachingService(project)
            before = copy.deepcopy(project.learner.__dict__)
            with patch.object(project.learner, 'correct', side_effect=AssertionError('calibration taught gold')):
                calibration = build_calibration(project, labeled('fit'), labeled('validation'))
            self.assertEqual(project.learner.__dict__, before)
            self.assertEqual(calibration.status(project.model_identity()), 'validated')
            service.submit('unknown', 'a-new-word')
            queue = review_queue(project, calibration=calibration)
            self.assertEqual(queue['calibration_status'], 'validated')
            self.assertEqual(queue['items'][0]['estimated_word_error_rate'], 1)
            ticket = service.predict('unknown')
            service.correct(ticket['prediction_id'], ['concept'])
            queue = review_queue(project, include_reviewed=True, calibration=calibration)
            self.assertEqual(queue['calibration_status'], 'stale')
            self.assertIsNone(queue['items'][0]['estimated_word_error_rate'])

    def test_brier_regression_gate_is_separate_from_ece_threshold(self):
        predictor = FrozenPredictor()
        fit = ([record(f'f-k{i}', f'k-fit-{i}', 'known') for i in range(100)]
               +[record(f'f-r{i}', f'r-fit-{i}', 'wrong') for i in range(100)])
        validation = ([record(f'v-k{i}', f'k-val-{i}', 'wrong') for i in range(100)]
                      +[record(f'v-r{i}', f'r-val-{i}', 'root-PL') for i in range(100)])
        calibration = build_calibration(predictor, fit, validation, config={**DEFAULTS, 'max_ece': 1.0})
        self.assertEqual(calibration.status(predictor.model_identity()), 'validation_failed')
        self.assertGreater(calibration.validation['estimated']['brier'], calibration.validation['constant_fit_prior']['brier'])


if __name__ == '__main__':
    unittest.main()
