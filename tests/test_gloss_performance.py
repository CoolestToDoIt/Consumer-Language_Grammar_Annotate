"""Bulk/online semantic equivalence and non-timing performance regressions."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from decipher.corpus import TextExample
from decipher.gloss import GlossExample, GlossLearner


def record(identifier, words, glosses):
    return GlossExample(TextExample(identifier, tuple(words)), tuple(glosses))


def annotations():
    anchors = record('anchors', ('tal', 'mir', 'vel', 'nim', 'café'), ('tree', 'bird', 'flower', 'stone', 'coffee'))
    return [
        anchors,
        record('plural-tree', ('talum',), ('tree-PL',)),
        record('plural-bird', ('mirum',), ('bird-PL',)),
        record('past-tree', ('zatal',), ('PST-tree',)),
        record('past-bird', ('zamir',), ('PST-bird',)),
        record('other-form', ('talen',), ('tree-DAT',)),
        record('ambiguity', ('tal',), ('tree-DIM',)),
        record('unicode', ('caféum',), ('coffee-PL',)),
        record('plural-tree', ('talum',), ('tree-PL',)),  # duplicate
        record('other-form', ('talen',), ('tree-LOC',)),  # revision removes DAT evidence
    ]


def probes():
    return TextExample('probe', ('velum', 'nimfin', 'zavel', 'tal', 'talen', 'café', 'caféum', 'unknownum'))


class CountingGlossLearner(GlossLearner):
    def __init__(self, *args, **kwargs):
        self.ranking_passes = 0
        super().__init__(*args, **kwargs)

    def _rules(self):
        if self._rule_cache is None:
            self.ranking_passes += 1
        return super()._rules()


class BulkGlossTests(unittest.TestCase):
    def test_bulk_matches_sequential_candidates_state_and_version_in_all_modes(self):
        for mode in ('memory', 'analogy', 'rules'):
            for bounds in ({}, {'max_rules': 3, 'paradigm_window': 2}):
                with self.subTest(mode=mode, **bounds):
                    sequential = GlossLearner(mode, **bounds)
                    bulk = GlossLearner(mode, **bounds)
                    for item in annotations():
                        sequential.correct(item.example, item.glosses)
                    self.assertIs(bulk.fit(iter(annotations())), bulk)
                    self.assertEqual(bulk.__dict__, sequential.__dict__)
                    self.assertEqual(bulk.predict(probes()), sequential.predict(probes()))
                    self.assertEqual(bulk.version, 9)
                    self.assertNotIn('tree-DAT', bulk.lexicon['talen'])

    def test_bulk_only_ranks_once_and_online_corrections_remain_ready(self):
        items = annotations()[:6]
        online = CountingGlossLearner()
        bulk = CountingGlossLearner()
        for item in items:
            online.correct(item.example, item.glosses)
        bulk.fit(items)
        self.assertEqual(online.ranking_passes, len(items))
        self.assertEqual(bulk.ranking_passes, 1)
        self.assertIsNotNone(bulk._rule_cache)
        before = copy.deepcopy(bulk.__dict__)
        bulk.predict(probes())
        self.assertEqual(bulk.__dict__, before)
        update = record('new-marker', ('talfin',), ('tree-ABL',))
        online.correct(update.example, update.glosses)
        bulk.correct(update.example, update.glosses)
        self.assertEqual(bulk.predict(probes()), online.predict(probes()))
        self.assertEqual(bulk.predict(probes())[1]['gloss'], 'stone-ABL')
        self.assertIsNotNone(bulk._rule_cache)

    def test_fit_appends_to_existing_state_and_is_idempotent(self):
        items = annotations()[:6]
        expected = GlossLearner()
        actual = CountingGlossLearner()
        for item in items:
            expected.correct(item.example, item.glosses)
        actual.fit(items[:2]).fit(item for item in items[2:])
        self.assertEqual(actual.predict(probes()), expected.predict(probes()))
        before = copy.deepcopy(actual.__dict__)
        actual.fit(items)
        self.assertEqual(actual.__dict__, before)

    def test_failed_input_keeps_successful_prefix_prepared_without_applying_bad_record(self):
        first = annotations()[0]
        expected = GlossLearner().fit([first])
        cases = [
            [first, GlossExample(TextExample('bad', ('tal', 'mir')), ('tree',))],
            [first, 'not a gloss record'],
            [first, GlossExample(TextExample('missing', ('tal',)), None)],
        ]
        for items in cases:
            with self.subTest(items=items):
                actual = GlossLearner()
                with self.assertRaises((TypeError, ValueError)):
                    actual.fit(iter(items))
                self.assertEqual(actual.__dict__, expected.__dict__)
                self.assertEqual(actual.predict(probes()), expected.predict(probes()))

    def test_generator_failure_leaves_equivalent_valid_prefix(self):
        items = annotations()[:4]
        def interrupted():
            yield from items
            raise RuntimeError('input stream stopped')
        actual = GlossLearner()
        with self.assertRaisesRegex(RuntimeError, 'input stream stopped'):
            actual.fit(interrupted())
        expected = GlossLearner().fit(items)
        self.assertEqual(actual.__dict__, expected.__dict__)
        self.assertIsNotNone(actual._rule_cache)

    def test_reused_id_with_different_source_is_rejected_like_correct(self):
        first = annotations()[0]
        invalid = record(first.example.id, ('different',), ('tree',))
        actual = GlossLearner()
        with self.assertRaisesRegex(ValueError, 'cannot change source'):
            actual.fit([first, invalid])
        self.assertEqual(actual.__dict__, GlossLearner().fit([first]).__dict__)

    def test_empty_fit_is_a_noop(self):
        learner = GlossLearner()
        before = copy.deepcopy(learner.__dict__)
        self.assertIs(learner.fit(iter(())), learner)
        self.assertEqual(before, learner.__dict__)

    def test_existing_v1_checkpoint_loads_with_one_ranking_and_saved_version(self):
        items = annotations()[:8]
        # Handwritten original schema, not serialized by the new save method.
        state = {'schema_version': 1, 'mode': 'rules', 'max_rules': 512,
                 'paradigm_window': 32, 'version': 42,
                 'records': [{'id': r.example.id, 'tokens': list(r.example.tokens), 'glosses': list(r.glosses)} for r in items]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'legacy.json.gz'
            with gzip.open(path, 'wt', encoding='utf-8') as handle:
                json.dump(state, handle, ensure_ascii=False)
            restored = CountingGlossLearner.load(path)
        expected = GlossLearner().fit(items)
        self.assertEqual(restored.predict(probes()), expected.predict(probes()))
        self.assertEqual(restored.version, 42)
        self.assertEqual(restored.ranking_passes, 1)
        self.assertIsNotNone(restored._rule_cache)

    def test_save_load_after_revisions_preserves_candidate_scores_for_every_mode(self):
        for mode in ('memory', 'analogy', 'rules'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                model = GlossLearner(mode).fit(annotations())
                path = Path(tmp) / 'model.json.gz'
                model.save(path)
                restored = GlossLearner.load(path)
                self.assertEqual(restored.__dict__, model.__dict__)
                self.assertEqual(restored.predict(probes()), model.predict(probes()))
                before = copy.deepcopy(restored.__dict__)
                restored.predict(probes())
                self.assertEqual(restored.__dict__, before)

    def test_legacy_duplicate_checkpoint_ids_remain_rejected(self):
        item = annotations()[0]
        row = {'id': item.example.id, 'tokens': list(item.example.tokens), 'glosses': list(item.glosses)}
        state = {'schema_version': 1, 'mode': 'rules', 'max_rules': 512,
                 'paradigm_window': 32, 'version': 2, 'records': [row, row]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'duplicate.json.gz'
            with gzip.open(path, 'wt') as handle:
                json.dump(state, handle)
            with self.assertRaisesRegex(ValueError, 'Duplicate checkpoint'):
                GlossLearner.load(path)


if __name__ == '__main__':
    unittest.main()
