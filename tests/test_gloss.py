import copy
from pathlib import Path
import tempfile
import unittest
from decipher.corpus import TextExample
from decipher.gloss import GlossLearner, load_gloss
from decipher.gloss_evaluate import evaluate_gloss, online_gloss


class GlossTests(unittest.TestCase):
    def test_reader_discards_answer_bearing_noninput_tiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'sample'
            path.write_text('\\t tal mir\n\\g tree bird\n\\l SECRET TRANSLATION\n\\m SECRET SEGMENTATION\n')
            records,stats=load_gloss(path)
            self.assertEqual(records[0].example.tokens,('tal','mir'))
            self.assertEqual(records[0].glosses,('tree','bird'))
            self.assertNotIn('SECRET',repr(records))
            path.write_text('\\t tal mir\n\\g tree\n')
            with self.assertRaisesRegex(ValueError,'2 words / 1 glosses'):
                load_gloss(path)
            self.assertEqual(load_gloss(path,skip_misaligned=True)[1]['misaligned'],1)

    def test_correction_transfers_suffix_and_prefix_to_grounded_root(self):
        for marked,new_word in [('talum','mirum'),('umtal','ummir')]:
            model=GlossLearner()
            model.correct(TextExample('anchors',('tal','mir')),('tree','bird'))
            public=TextExample('probe',(new_word,))
            self.assertIsNone(model.predict(public)[0]['gloss'])
            model.correct(TextExample('lesson',(marked,)),('tree-PL',))
            self.assertEqual(model.predict(public)[0]['gloss'],'bird-PL')
            self.assertEqual(model.predict(public)[0]['candidates'][0]['kind'],'rule')

    def test_predictions_do_not_mutate_and_ungrounded_roots_remain_unknown(self):
        model=GlossLearner()
        model.correct(TextExample('root',('tal',)),('tree',))
        model.correct(TextExample('plural',('talum',)),('tree-PL',))
        before=copy.deepcopy(model.__dict__)
        self.assertIsNone(model.predict(TextExample('probe',('unknownum',)))[0]['gloss'])
        self.assertEqual(model.__dict__,before)
        with self.assertRaises(TypeError):
            model.predict({'tokens':['tal'],'glosses':['tree']})

    def test_duplicates_revisions_and_resume(self):
        model=GlossLearner()
        example=TextExample('one',('tal',))
        self.assertTrue(model.correct(example,('tree',)))
        self.assertFalse(model.correct(example,('tree',)))
        model.correct(example,('bird',))
        self.assertEqual(model.predict(example)[0]['gloss'],'bird')
        self.assertNotIn('tree',model.lexicon['tal'])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'model.gz'
            model.save(path)
            restored=GlossLearner.load(path)
        self.assertEqual(model.__dict__,restored.__dict__)

    def test_evaluation_filters_overlap_and_online_labels_arrive_later(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            train=directory/'train'
            dev=directory/'dev'
            train.write_text('\\t tal mir\n\\g tree bird\n\n\\t talum\n\\g tree-PL\n\n\\t tal\n\\g tree\n')
            dev.write_text('\\t tal mir\n\\g tree bird\n\n\\t mirum\n\\g bird-PL\n')
            report=evaluate_gloss(train,dev,directory/'report.json')
            self.assertEqual(report['filters']['source_overlaps_excluded'],1)
            self.assertEqual(report['models']['rules']['word_accuracy'],1)
            streaming=online_gloss(train,dev,directory/'stream',support=1,stream_size=2,delays=(1,),probe_every=1)
            for row in streaming['runs']:
                self.assertEqual(row['pending'],1)
                self.assertEqual(row['curve'][-1]['arrived_sentence_labels'],1)

if __name__=='__main__':
    unittest.main()
