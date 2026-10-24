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
        self.assertEqual(online.ranking_passes, len(items)-1)  # anchors add no rules
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
            [first, GlossExample(TextExample('bad', ('tal', 42)), ('tree', 'bird'))],
            [first, GlossExample(TextExample('bad', ['tal']), ('tree',))],
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

    def test_malformed_checkpoint_metadata_and_annotation_types_are_rejected(self):
        valid = {'schema_version': 1, 'mode': 'rules', 'max_rules': 512,
                 'paradigm_window': 32, 'version': 1,
                 'records': [{'id': 'one', 'tokens': ['tal'], 'glosses': ['tree']}]}
        cases = [[], {**valid, 'schema_version': True}, {**valid, 'records': {}},
                 *[{**valid, 'version': value} for value in (-1, 0, 1.5, True, '1', None)]]
        for field,value in [('tokens', 'tal'), ('glosses', 'tree'), ('tokens', [42]),
                            ('tokens', ['']), ('id', []), ('glosses', ['two labels'])]:
            state = copy.deepcopy(valid)
            state['records'][0][field] = value
            cases.append(state)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'malformed.json.gz'
            for state in cases:
                with self.subTest(state=state):
                    with gzip.open(path, 'wt') as handle:
                        json.dump(state, handle)
                    before = path.read_bytes()
                    with self.assertRaises(ValueError):
                        GlossLearner.load(path)
                    self.assertEqual(path.read_bytes(), before)


class AnalogyIndexTests(unittest.TestCase):
    @staticmethod
    def brute_force(model, word):
        query = model._grams(word)
        def similarity(known):
            grams = model.grams[known]
            return len(grams & query) / len(grams | query)
        nearest = min(model.lexicon, key=lambda known: (-similarity(known), known))
        counts = model.lexicon[nearest]
        gloss = min(counts, key=lambda value: (-counts[value], value))
        return [{'gloss': gloss, 'score': similarity(nearest), 'kind': 'analogy', 'anchor': nearest}]

    def test_matches_exhaustive_oracle_on_unicode_and_randomized_words(self):
        import random
        rng = random.Random(2048)
        alphabet = 'abcABCéøжя日α!?-'
        words = sorted({''.join(rng.choices(alphabet, k=rng.randint(1, 18))) for _ in range(700)})
        model = GlossLearner('analogy').fit([record('vocabulary', words, [f'label{i}' for i in range(len(words))])])
        queries = [''.join(rng.choices(alphabet, k=rng.randint(1, 24))) for _ in range(250)]
        queries += ['☃', 'e\u0301', '日本語', 'UNKNOWN', '^', '$', '']
        for word in queries:
            if word in model.lexicon:
                continue
            with self.subTest(word=word):
                self.assertEqual(model.word_candidates(word), self.brute_force(model, word))

    def test_no_overlap_and_similarity_ties_preserve_lexical_order(self):
        model = GlossLearner('analogy').fit([record('words', ('cat', 'bat', 'aaaa', 'aaaaa'), ('cat', 'bat', 'short', 'long'))])
        for word in ('hat', '☃', 'aaaaaa'):
            self.assertEqual(model.word_candidates(word), self.brute_force(model, word))
        self.assertEqual(model.word_candidates('hat')[0]['anchor'], 'bat')
        self.assertEqual(model.word_candidates('☃')[0]['anchor'], 'aaaa')
        self.assertEqual(model.word_candidates('☃')[0]['score'], 0)
        self.assertEqual(model.word_candidates('aaaaaa')[0]['anchor'], 'aaaa')
        self.assertEqual(model.word_candidates('aaaaaa')[0]['score'], 1)

    def test_index_tracks_append_revision_duplicate_and_checkpoint_reload(self):
        model = GlossLearner('analogy').fit(annotations()[:6])
        model.fit(annotations()[6:])
        extra = record('extra', ('nimfin', 'sun'), ('stone-ABL', 'sun'))
        model.correct(extra.example, extra.glosses)
        self.assertFalse(model.correct(extra.example, extra.glosses))
        model.correct(extra.example, ('stone-DAT', 'sun'))
        expected = {}
        for word, grams in model.grams.items():
            for gram in grams:
                expected.setdefault(gram, set()).add(word)
        self.assertEqual(dict(model._gram_index), expected)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'indexed.json.gz'
            model.save(path)
            restored = GlossLearner.load(path)
        self.assertEqual(restored.__dict__, model.__dict__)
        for query in ('sunum', 'nimfinen', '☃'):
            self.assertEqual(restored.word_candidates(query), self.brute_force(restored, query))

    def test_unknown_queries_do_not_insert_postings_or_change_state(self):
        model = GlossLearner('analogy').fit(annotations())
        before = copy.deepcopy(model.__dict__)
        for word in ('☃', 'UNKNOWN', 'velum', '☃☃☃'):
            model.word_candidates(word)
        self.assertEqual(model.__dict__, before)

    def test_positive_overlap_does_not_scan_unrelated_lexicon_entries(self):
        model = GlossLearner('analogy').fit([record('words', ('abc', 'xyz', '日本', '☀☀'), ('first', 'second', 'third', 'fourth'))])
        class CountingGrams(dict):
            def __init__(self, values):
                super().__init__(values)
                self.reads = []
            def __getitem__(self, key):
                self.reads.append(key)
                return super().__getitem__(key)
        model.grams = CountingGrams(model.grams)
        result = model.word_candidates('abd')
        self.assertEqual(result[0]['anchor'], 'abc')
        self.assertTrue(model.grams.reads)
        self.assertEqual(set(model.grams.reads), {'abc'})


class RuleIndexTests(unittest.TestCase):
    def test_index_matches_exhaustive_affix_filter_in_rank_order(self):
        import random
        rng = random.Random(218)
        model = GlossLearner().fit(annotations())
        words = ['', 'velum', 'zavel', 'nimfin', 'caféum', 'unknown', '☃']
        words += [''.join(rng.choices('talumzé☃', k=rng.randrange(1, 20))) for _ in range(300)]
        for word in words:
            expected = [rule for rule in model._rules()
                        if (word.startswith(rule[2]) if rule[0] == 'prefix' else word.endswith(rule[2]))]
            self.assertEqual(model._matching_rules(word), expected)

    def test_candidates_match_full_rule_scan_after_updates_revisions_and_reload(self):
        class ExhaustiveLearner(GlossLearner):
            def _matching_rules(self, word):
                return self._rules()
        actual = GlossLearner()
        expected = ExhaustiveLearner()
        for item in annotations():
            actual.correct(item.example, item.glosses)
            expected.correct(item.example, item.glosses)
            self.assertEqual(actual.predict(probes()), expected.predict(probes()))
        before = copy.deepcopy(actual.__dict__)
        actual.predict(probes())
        self.assertEqual(actual.__dict__, before)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'model.gz'
            actual.save(path)
            restored = GlossLearner.load(path)
        self.assertEqual(restored.__dict__, actual.__dict__)
        self.assertEqual(restored.predict(probes()), expected.predict(probes()))


class IncrementalRankingTests(unittest.TestCase):
    @staticmethod
    def exhaustive(model):
        return sorted(model.rule_evidence, key=lambda rule: (
            -len(model.rule_evidence[rule]),
            sum(len(rule[i]) for i in (1, 2, 4, 5)), rule))[:model.max_rules]

    def test_every_update_and_revision_matches_exhaustive_ranking(self):
        import random
        rng = random.Random(491)
        items = []
        for index in range(120):
            stem = rng.choice(('tal', 'mir', 'vel', 'nim', 'café', 'doran'))
            marker, label = rng.choice((('', ''), ('um', '-PL'), ('en', '-DAT'), ('fin', '-ABL')))
            items.append(record(str(index), (stem + marker,), (stem + label,)))
        for bound in (1, 3, 17, 512):
            model = GlossLearner(max_rules=bound)
            for item in items + [record('0', items[0].example.tokens, ('revised-LOC',))]:
                model.correct(item.example, item.glosses)
                self.assertEqual(model._rules(), self.exhaustive(model))
                self.assertFalse(model._dirty_rules)
            bulk = GlossLearner(max_rules=bound).fit(items + [record('0', items[0].example.tokens, ('revised-LOC',))])
            self.assertEqual(model.__dict__, bulk.__dict__)

    def test_bounded_selection_matches_full_sort_across_strategy_boundary(self):
        for count in (0, 1, 255, 256, 257, 3000):
            model = GlossLearner(max_rules=64)
            for index in range(count):
                rule = ('suffix', '', str(index), 'suffix', '', '-PL')
                model.rule_evidence[rule].update(str(n) for n in range(1 + index % 7))
            model._dirty_rules = set(model.rule_evidence)
            model._rule_cache = None
            self.assertEqual(model._rules(), self.exhaustive(model))
            self.assertFalse(model._dirty_rules)

    def test_unchanged_support_keeps_prepared_ranking(self):
        model = CountingGlossLearner().fit(annotations()[:3])
        ranking = model._rule_cache
        passes = model.ranking_passes
        item = record('repeat', ('talum', 'mir'), ('tree-PL', 'bird'))
        model.correct(item.example, item.glosses)
        self.assertIs(model._rule_cache, ranking)
        self.assertEqual(model.ranking_passes, passes)
        self.assertEqual(model.lexicon['talum']['tree-PL'], 2)


if __name__ == '__main__':
    unittest.main()
