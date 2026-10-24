import copy
import json
from pathlib import Path
import tempfile
import unittest

from decipher.corpus import Analysis, AnnotatedSentence, TextExample, read_conllu, read_corpus, read_jsonl, sentence_dict
from decipher.corpus_learner import CorpusLearner
from decipher.corpus_evaluate import evaluate_corpus, Metrics


def sentence(identifier, words, lemmas, upos='NOUN', feats=('Number=Plur',)):
    return AnnotatedSentence(TextExample(identifier, tuple(words)), tuple(Analysis(lemma, upos, feats) for lemma in lemmas))


def write_jsonl(path, sentences):
    path.write_text(''.join(json.dumps(sentence_dict(s), ensure_ascii=False)+'\n' for s in sentences))


class CorpusTests(unittest.TestCase):
    def test_conllu_word_alignment_unicode_and_final_sentence(self):
        text = '# sent_id = unicode\n1-2\tau\t_\t_\t_\t_\t_\t_\t_\t_\n1\ta\ta\tADP\t_\t_\t0\troot\t_\t_\n2\tle\tle\tDET\t_\tNumber=Sing|Gender=Masc\t1\tdep\t_\t_\n2.1\tmissing\t_\t_\t_\t_\t_\t_\t_\t_\n\n# sent_id = second\n1\tcafe\u0301\tcafé\tNOUN\t_\t_\t0\troot\t_\t_'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'fixture.conllu'
            path.write_text(text)
            records = list(read_conllu(path))
        self.assertEqual(records[0].example.tokens, ('a', 'le'))
        self.assertEqual(records[0].analyses[1].feats, ('Gender=Masc', 'Number=Sing'))
        self.assertEqual(records[1].example.tokens, ('café',))

    def test_rejects_broken_alignment_and_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'fixture.jsonl'
            row = sentence_dict(sentence('x', ['birds'], ['bird']))
            path.write_text(json.dumps(dict(row, analyses=[])))
            with self.assertRaisesRegex(ValueError, 'aligned'):
                list(read_jsonl(path))
            write_jsonl(path, [sentence('x', ['birds'], ['bird'])]*2)
            with self.assertRaisesRegex(ValueError, 'Duplicate sentence ID'):
                list(read_corpus(path))
            malformed = Path(tmp)/'fixture.conllu'
            malformed.write_text('1 birds bird NOUN _ _ 0 root _ _\n')
            with self.assertRaisesRegex(ValueError, '10 tab-separated'):
                list(read_conllu(malformed))

    def test_learning_curve_uses_only_released_training_labels(self):
        from decipher.corpus_evaluate import learning_curve
        training = [sentence('a', ['birds'], ['bird']), sentence('b', ['trees'], ['tree']), sentence('c', ['stones'], ['stone'])]
        probes = [sentence('fresh', ['flowers'], ['flower'])]
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            write_jsonl(directory/'train.jsonl', training)
            write_jsonl(directory/'dev.jsonl', probes)
            report = learning_curve(directory/'train.jsonl', directory/'dev.jsonl', directory/'curve.json', budgets=(1, 2))
        self.assertEqual([p['sentence_labels'] for p in report['points']], [0, 1, 2, 3])
        self.assertEqual([p['token_labels'] for p in report['points']], [0, 1, 2, 3])
        self.assertEqual(report['points'][0]['scores']['affix']['held_out']['joint_accuracy'], 0)
        self.assertEqual(report['points'][-1]['scores']['affix']['held_out']['joint_accuracy'], 1)
        self.assertEqual(report['points'][0]['scores']['affix']['training_recall']['joint_accuracy'], None)
        self.assertEqual(report['evaluation_sentences'], 1)

    def test_corpus_cli_train_analyze_correct_and_reload(self):
        import subprocess
        import sys
        import gzip
        sample = [sentence('a', ['birds'], ['bird'])]
        revision = [sentence('a', ['birds'], ['bird'], upos='CUSTOM', feats=('Category=New',))]
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            train_file, annotations, model = directory/'train.jsonl', directory/'revision.jsonl', directory/'model.gz'
            write_jsonl(train_file, sample)
            write_jsonl(annotations, revision)
            commands = [
                ['train', '--train', str(train_file), '--model', str(model)],
                ['analyze', '--model', str(model), '--text', 'birds'],
                ['correct', '--model', str(model), '--annotations', str(annotations)],
                ['correct', '--model', str(model), '--annotations', str(annotations)],
                ['analyze', '--model', str(model), '--text', 'birds']]
            outputs = []
            for command in commands:
                result = subprocess.run([sys.executable, '-m', 'decipher.app', 'corpus', *command], text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                outputs.append(result.stdout)
            self.assertEqual(json.loads(outputs[1])['analyses'][0]['upos'], 'NOUN')
            self.assertEqual(json.loads(outputs[-1])['analyses'][0]['upos'], 'CUSTOM')
            self.assertIn('Applied 0', outputs[3])
            with gzip.open(model, 'rt') as handle:
                state = json.load(handle)
            self.assertEqual(state['version'], 2)
            self.assertEqual(len(state['records']), 1)

    def test_exact_teacher_answer_is_recalled_despite_lexical_majority(self):
        learner = CorpusLearner()
        for i in range(10):
            item = sentence(f'common-{i}', ['can'], ['can'], upos='NOUN', feats=())
            learner.correct(item.example, item.analyses)
        correction = sentence('teacher', ['can'], ['can'], upos='AUX', feats=('Mood=Ind',))
        learner.correct(correction.example, correction.analyses)
        self.assertEqual(learner.predict(correction.example), correction.analyses)
        self.assertEqual(learner.predict(correction.example, verified_memory=False)[0].upos, 'NOUN')
        amended = sentence('common-0', ['can'], ['can'], upos='VERB', feats=())
        learner.correct(amended.example, amended.analyses)
        self.assertEqual(learner.predict(amended.example), amended.analyses)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'model.gz'
            learner.save(path)
            self.assertEqual(CorpusLearner.load(path).predict(amended.example), amended.analyses)

    def test_suffix_rule_transfers_to_unseen_word(self):
        learner = CorpusLearner()
        for i, (word, lemma) in enumerate((('birds', 'bird'), ('trees', 'tree'), ('stones', 'stone'))):
            item = sentence(str(i), [word], [lemma])
            learner.correct(item.example, item.analyses)
        fresh = TextExample('new', ('flowers',))
        self.assertNotIn('flowers', learner.lexicon)
        prediction = learner.predict(fresh)[0]
        self.assertEqual(prediction, Analysis('flower', 'NOUN', ('Number=Plur',)))
        self.assertNotEqual(learner.predict(fresh, model='lexicon')[0].lemma, 'flower')
        self.assertIsNone(learner.predict(fresh, model='memory')[0].lemma)

    def test_predictions_are_gold_free_and_do_not_change_state(self):
        learner = CorpusLearner()
        item = sentence('train', ['birds'], ['bird'])
        learner.correct(item.example, item.analyses)
        before = copy.deepcopy(learner.__dict__)
        public = TextExample('probe', ('flowers',))
        saved = learner.predict(public)
        self.assertEqual(before, learner.__dict__)
        private_one = AnnotatedSentence(public, (Analysis('flower', 'NOUN', ('Number=Plur',)),))
        private_two = AnnotatedSentence(public, (Analysis('anything', 'CUSTOM', ()),))
        self.assertEqual(learner.predict(private_one.example), learner.predict(private_two.example))
        with self.assertRaises(TypeError):
            learner.predict(private_one)
        learner.correct(public, private_two.analyses)
        self.assertEqual(learner.predict(public)[0].upos, 'CUSTOM')
        self.assertEqual(saved[0], Analysis('flower', 'NOUN', ('Number=Plur',)))

    def test_revision_idempotency_and_resume(self):
        learner = CorpusLearner()
        item = sentence('x', ['birds'], ['bird'])
        self.assertTrue(learner.correct(item.example, item.analyses))
        self.assertFalse(learner.correct(item.example, item.analyses))
        revised = (Analysis('bird', 'CUSTOM', ('Label=Other',)),)
        self.assertTrue(learner.correct(item.example, revised))
        self.assertEqual(learner.token_count, 1)
        self.assertEqual(learner.predict(item.example), revised)
        with self.assertRaises(ValueError):
            learner.correct(TextExample('x', ('trees',)), revised)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'model.json.gz'
            learner.save(path)
            loaded = CorpusLearner.load(path)
        self.assertEqual(loaded.__dict__, learner.__dict__)

    def test_unannotated_fields_have_explicit_denominators(self):
        metrics = Metrics()
        gold = AnnotatedSentence(TextExample('missing', ('x',)), (Analysis(None, 'NOUN', ()),))
        metrics.add(gold, (Analysis('x', 'NOUN', ()),), set())
        result = metrics.result()
        self.assertIsNone(result['lemma_accuracy'])
        self.assertIsNone(result['joint_accuracy'])
        self.assertEqual(result['upos_accuracy'], 1)
        self.assertEqual(result['counts']['oov_tokens'], 1)

    def test_evaluation_excludes_overlap_and_uses_frozen_model(self):
        training = [sentence('train', ['birds'], ['bird']), sentence('train2', ['trees'], ['tree']), sentence('train3', ['stones'], ['stone'])]
        probes = [sentence('duplicate-source', ['birds'], ['bird']), sentence('fresh', ['flowers'], ['flower'])]
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            write_jsonl(directory/'train.jsonl', training)
            write_jsonl(directory/'eval.jsonl', probes)
            report = evaluate_corpus(directory/'train.jsonl', directory/'eval.jsonl', directory/'report.json', model_path=directory/'model.gz')
            loaded = CorpusLearner.load(directory/'model.gz')
            self.assertNotIn('fresh', loaded.records)
            self.assertEqual(len(loaded.records), 3)
        self.assertEqual(report['excluded_train_overlap_sentences'], 1)
        self.assertEqual(report['models']['affix']['joint_accuracy'], 1)
        self.assertEqual(report['models']['affix']['counts']['tokens'], 1)
        self.assertEqual(report['models']['lexicon']['joint_accuracy'], 0)

if __name__ == '__main__':
    unittest.main()
