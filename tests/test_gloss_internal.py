"""Isolated internal-edit transfer, grounding, equivalence and restart fixtures."""
import copy
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from decipher.corpus import TextExample
from decipher.gloss import GlossExample, GlossLearner, lexical_key, transform
from decipher.gloss_internal import InternalGlossOverlay, StaleOverlayError, internal_edit


def record(identifier, words, glosses):
    return GlossExample(TextExample(identifier, tuple(words)), tuple(glosses))


def replacement_model(**config):
    return GlossLearner(**config).fit([
        record('anchors', ('man', 'tal', 'ber'), ('person', 'tree', 'branch-PL')),
        record('plural', ('men',), ('person-PL',)),
    ])


class InternalEditTests(unittest.TestCase):
    def test_canonical_internal_replacement_insertion_deletion_and_boundaries(self):
        for first, second, expected in (
                ('man', 'men', ('a', 'e')), ('tal', 'taxl', ('', 'x')),
                ('taal', 'tal', ('a', '')), ('aaaa', 'aaa', ('a', '')),
                ('bär', 'bör', ('ä', 'ö')), ('tal', 'mal', None),
                ('tal', 'tam', None), ('a', 'e', None), ('same', 'same', None),
                ('', 'word', None)):
            with self.subTest(first=first, second=second):
                self.assertEqual(internal_edit(first, second), expected)

    def test_internal_replacement_transfers_only_from_observed_anchors(self):
        base = replacement_model()
        overlay = InternalGlossOverlay(base)
        public = TextExample('unseen', ('tel', 'bar', 'zep'))
        self.assertEqual([row['gloss'] for row in base.predict(public)], [None, None, None])
        predictions = overlay.predict(public)
        self.assertEqual([row['gloss'] for row in predictions], ['tree-PL', 'branch', None])
        candidate = predictions[0]['candidates'][0]
        self.assertEqual(candidate['kind'], 'internal_rule')
        self.assertEqual(candidate['anchor'], 'tal')
        self.assertEqual(candidate['rule'], ['internal', 'a', 'e', 'suffix', '', '-PL'])
        self.assertEqual(candidate['support_lexemes'], 1)
        self.assertAlmostEqual(candidate['score'], 1/1.5)

    def test_middle_insertion_and_deletion_deduplicate_identical_anchor_paths(self):
        inserted = GlossLearner().fit([
            record('anchors', ('tal', 'mir'), ('tree', 'bird')),
            record('marked', ('taxl',), ('tree-PL',)),
        ])
        overlay = InternalGlossOverlay(inserted)
        self.assertEqual(overlay.predict(TextExample('probe', ('mixr',)))[0]['gloss'], 'bird-PL')
        deleted = GlossLearner().fit([
            record('anchors', ('maam', 'taal'), ('person', 'tree')),
            record('marked', ('mam',), ('person-PL',)),
        ])
        overlay = InternalGlossOverlay(deleted)
        candidate = overlay.predict(TextExample('probe', ('tal',)))[0]['candidates'][0]
        self.assertEqual(candidate['gloss'], 'tree-PL')
        self.assertAlmostEqual(candidate['score'], 1/1.4)
        recoveries = [row for row in overlay.recoveries('tal') if row['rule'][0] == 'internal']
        self.assertEqual(len(recoveries), 1)
        self.assertEqual(recoveries[0]['anchors'], ['taal'])

    def test_competing_grammatical_tags_and_unicode_have_deterministic_candidates(self):
        base = GlossLearner().fit([
            record('anchors', ('man', 'cat', 'tal'), ('person', 'cat', 'tree')),
            record('one', ('men',), ('person-PL',)),
            record('two', ('cet',), ('cat-DU',)),
        ])
        candidates = InternalGlossOverlay(base).predict(TextExample('probe', ('tel',)))[0]['candidates']
        self.assertEqual([row['gloss'] for row in candidates], ['tree-DU', 'tree-PL'])
        self.assertEqual(candidates[0]['score'], candidates[1]['score'])
        unicode_model = GlossLearner().fit([
            record('anchors', ('bär', 'täl'), ('bear', 'flower')),
            record('plural', ('bör',), ('bear-PL',)),
        ])
        self.assertEqual(InternalGlossOverlay(unicode_model).predict(TextExample('accent', ('töl',)))[0]['gloss'], 'flower-PL')

    def test_known_form_full_candidates_are_unchanged_even_when_rules_are_displaced(self):
        base = replacement_model(max_rules=2)
        base.correct(TextExample('ambiguity', ('tal',)), ('tree-DIM',))
        overlay = InternalGlossOverlay(base)
        example = TextExample('known', tuple(base.lexicon))
        self.assertEqual(overlay.predict(example), base.predict(example))
        self.assertEqual(len(overlay.selected_rules), 2)
        self.assertTrue(any(rule[0] == 'internal' for rule in overlay.selected_rules))

    def test_no_internal_evidence_requires_exact_complete_baseline_equivalence(self):
        base = GlossLearner().fit([
            record('anchors', ('tal', 'mir', 'vel'), ('tree', 'bird', 'flower')),
            record('plural', ('talum',), ('tree-PL',)),
            record('case', ('talen',), ('tree-DAT',)),
            record('prefix', ('umtal',), ('PST-tree',)),
        ])
        overlay = InternalGlossOverlay(base)
        self.assertEqual(overlay.diagnostics()['internal_hypotheses'], 0)
        self.assertEqual(overlay.selected_rules, tuple(base._rules()))
        probe = TextExample('probe', ('tal', 'mir', 'mirum', 'miren', 'ummir', 'unknown', '.', 'velum'))
        self.assertEqual(overlay.predict(probe), base.predict(probe))

    def test_prediction_and_recovery_leave_model_overlay_and_rng_unchanged(self):
        base = replacement_model()
        overlay = InternalGlossOverlay(base)
        before = copy.deepcopy(base.__dict__)
        derived = {key: copy.deepcopy(value) for key, value in overlay.__dict__.items() if key != 'base'}
        rng = random.getstate()
        with (patch.object(overlay, 'prepare', side_effect=AssertionError('deferred preparation')),
              patch.object(base, '_rules', side_effect=AssertionError('ranking during prediction'))):
            overlay.predict(TextExample('probe', ('tel', 'bar', 'man', 'unknown')))
            overlay.recoveries('tel')
        self.assertEqual(base.__dict__, before)
        self.assertEqual({key: value for key, value in overlay.__dict__.items() if key != 'base'}, derived)
        self.assertEqual(random.getstate(), rng)
        with self.assertRaises(TypeError):
            overlay.predict(record('private', ('tel',), ('tree-PL',)))

    def test_duplicate_feedback_is_idempotent_and_revisions_remove_old_internal_evidence(self):
        base = replacement_model()
        overlay = InternalGlossOverlay(base)
        state = copy.deepcopy(base.__dict__)
        self.assertFalse(base.correct(TextExample('plural', ('men',)), ('person-PL',)))
        self.assertEqual(base.__dict__, state)
        self.assertEqual(overlay.predict(TextExample('probe', ('tel',)))[0]['gloss'], 'tree-PL')
        base.correct(TextExample('plural', ('men',)), ('person-DU',))
        with self.assertRaises(StaleOverlayError):
            overlay.predict(TextExample('probe', ('tel',)))
        self.assertIs(overlay.prepare(), overlay)
        self.assertEqual(overlay.predict(TextExample('probe', ('tel',)))[0]['gloss'], 'tree-DU')
        self.assertFalse(any(rule[5] == '-PL' for rule in overlay._internal_evidence))

    def test_configuration_changes_are_stale_and_context_modes_are_rejected(self):
        base = replacement_model()
        overlay = InternalGlossOverlay(base)
        base.mode = 'memory'
        with self.assertRaises(StaleOverlayError):
            overlay.recoveries('tel')
        with self.assertRaises(ValueError):
            overlay.prepare()
        for model in (GlossLearner('memory'), GlossLearner('analogy'), GlossLearner(contextual=True)):
            with self.assertRaises(ValueError):
                InternalGlossOverlay(model)
        with self.assertRaises(TypeError):
            InternalGlossOverlay('not a learner')

    def test_schema_one_save_load_reconstructs_all_overlay_state_and_candidates(self):
        base = replacement_model()
        base.correct(TextExample('plural', ('men',)), ('person-DU',))
        overlay = InternalGlossOverlay(base)
        before = copy.deepcopy(base.__dict__)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'base.json.gz'
            base.save(path)
            restored = InternalGlossOverlay.from_checkpoint(path)
        self.assertEqual(base.__dict__, before)
        self.assertEqual(restored.base.__dict__, base.__dict__)
        self.assertEqual(restored.selected_rules, overlay.selected_rules)
        self.assertEqual(restored._internal_evidence, overlay._internal_evidence)
        self.assertEqual(restored.predict(TextExample('probe', ('tel', 'bar', 'man', 'zep'))),
                         overlay.predict(TextExample('probe', ('tel', 'bar', 'man', 'zep'))))

    def test_union_rank_and_recovery_index_match_exhaustive_reference(self):
        base = GlossLearner(max_rules=7).fit([
            record('root', ('man', 'tal', 'maam', 'taal'), ('person', 'tree', 'person', 'tree')),
            record('plural', ('men', 'mam'), ('person-PL', 'person-PL')),
            record('case', ('talen',), ('tree-DAT',)),
        ])
        overlay = InternalGlossOverlay(base)
        expected = sorted(overlay._evidence, key=lambda rule: (
            -len(overlay._evidence[rule]), sum(len(rule[index]) for index in (1, 2, 4, 5)), rule))[:7]
        self.assertEqual(overlay.selected_rules, tuple(expected))
        for word in ('tel', 'tal', 'telen', 'talm', 'tael', 'talum', 'taaal', 'x'):
            exhaustive = []
            for rule in expected:
                anchors = set()
                if rule[0] == 'internal':
                    for position in range(1, len(word)):
                        end = position+len(rule[2])
                        if end < len(word) and word[position:end] == rule[2]:
                            anchor = word[:position]+rule[1]+word[end:]
                            if anchor in base.lexicon and anchor != word:
                                anchors.add(anchor)
                else:
                    anchor = transform(word, rule[0], rule[2], rule[1])
                    if anchor and anchor in base.lexicon and anchor != word:
                        anchors.add(anchor)
                if anchors:
                    exhaustive.append((rule, tuple(sorted(anchors))))
            self.assertEqual(overlay._recoveries(word), exhaustive)
            for candidate in overlay.word_candidates(word):
                self.assertIn(candidate['anchor'], base.lexicon)
                self.assertTrue(any(lexical_key(candidate['gloss']) == lexical_key(gloss)
                                    for gloss in base.lexicon[candidate['anchor']]))


if __name__ == '__main__':
    unittest.main()
