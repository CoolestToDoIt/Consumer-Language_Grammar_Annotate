import tempfile
import unittest
from pathlib import Path
from decipher.corpus import TextExample
from decipher.gloss import GlossExample, GlossLearner
from decipher.gloss_backoff import BackoffGlossLearner, surface_key


def record(identifier, tokens, glosses):
    return GlossExample(TextExample(identifier, tuple(tokens)), tuple(glosses))


TRAIN = [record('a', ['tal', 'mir'], ['tree', 'bird']),
         record('b', ['talum', 'esizaƛ’'], ['tree-PL', 'tell-CSL']),
         record('c', ['miri'], ['bird-ERG'])]


class BackoffTests(unittest.TestCase):
    def test_surface_key_strips_punctuation_but_keeps_apostrophe_letters(self):
        self.assertEqual(surface_key('«Tal,»'), 'tal')
        self.assertEqual(surface_key('esizaƛ’.'), 'esizaƛ’')
        self.assertEqual(surface_key(').'), '')

    def test_unseen_punctuated_and_capitalized_forms_reuse_taught_glosses(self):
        model = BackoffGlossLearner().fit(TRAIN)
        rows = model.predict(TextExample('p', ('Tal,', 'esizaƛ’.', 'mir')))
        self.assertEqual([row['gloss'] for row in rows], ['tree', 'tell-CSL', 'bird'])
        self.assertEqual([row['known_form'] for row in rows], [False, False, True])
        self.assertEqual(rows[0]['candidates'][0]['kind'], 'normalized_lexical')
        baseline = GlossLearner().fit(TRAIN).predict(TextExample('p', ('Tal,', 'esizaƛ’.')))
        self.assertEqual([row['gloss'] for row in baseline], [None, None])

    def test_rules_retry_on_normalized_spelling(self):
        model = BackoffGlossLearner().fit(TRAIN)
        self.assertEqual(model.predict(TextExample('p', ('Miri.',)))[0]['gloss'], 'bird-ERG')
        self.assertEqual(model.predict(TextExample('q', ('mirum,',)))[0]['gloss'], 'bird-PL')

    def test_known_forms_and_ungrounded_words_are_unchanged(self):
        base, backoff = GlossLearner().fit(TRAIN), BackoffGlossLearner().fit(TRAIN)
        example = TextExample('p', ('tal', 'talum', 'zzz', ').'))
        self.assertEqual(base.predict(example), backoff.predict(example))

    def test_revision_rebuilds_surface_lexicon_and_checkpoint_round_trips(self):
        model = BackoffGlossLearner().fit(TRAIN)
        model.correct(TRAIN[0].example, ('wood', 'bird'))
        self.assertEqual(model.predict(TextExample('p', ('Tal!',)))[0]['gloss'], 'wood')
        with tempfile.TemporaryDirectory() as tmp:
            model.save(Path(tmp)/'m.gz')
            loaded = BackoffGlossLearner.load(Path(tmp)/'m.gz')
        self.assertEqual(loaded.predict(TextExample('p', ('Tal!',)))[0]['gloss'], 'wood')


if __name__ == '__main__':
    unittest.main()
