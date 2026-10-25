import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from decipher.gloss_web import GlossWebApp
from decipher.project import LanguageProject

ROOT = Path(__file__).resolve().parents[1]


class PerformanceReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = LanguageProject.create(Path(self.tmp.name) / 'p.dproj', 'Velari', 'und')

    def test_each_first_annotation_is_scored_before_it_is_taught(self):
        # tal is new (untaught), then known; talum is new but follows the
        # tal/mir -> -um pattern taught by mirum.
        self.project.add_corpus('a.tsv', 'tal\ttree\nmir\tbird\nmirum\tbird-PL\ntal\ttree\ntalum\ttree-PL\nvel\tflower', 'tsv')
        result = self.project.performance()
        self.assertEqual((result['sentences'], result['words']), (6, 6))
        self.assertEqual(result['by_kind']['known'], {'words': 1, 'right': 1})
        self.assertEqual(result['by_kind']['pattern'], {'words': 1, 'right': 1})
        self.assertEqual(result['counts']['accepted'], 2)
        self.assertEqual(result['teach_once'], 1.0)
        self.assertAlmostEqual(result['curve'][-1]['sentences'], 6)

    def test_revisions_are_applied_but_not_scored(self):
        self.project.add_corpus('a.tsv', 'tal\ttree\ntal', 'tsv')
        second = next(row['id'] for row in self.project.queue() if not row['annotated'])
        self.project.correct(second, ['tree'])
        self.project.correct(second, ['wood'])
        result = self.project.performance()
        self.assertEqual(result['sentences'], 2)
        self.assertEqual(result['counts']['accepted'], 1)

    def test_empty_project_has_no_rates(self):
        result = self.project.performance()
        self.assertEqual(result['words'], 0)
        self.assertIsNone(result['accepted'])
        self.assertEqual(result['curve'], [])

    def test_endpoint_lists_every_language_without_an_open_project(self):
        self.project.add_corpus('a.tsv', 'tal\ttree\ntal\ttree', 'tsv')
        LanguageProject.create(Path(self.tmp.name) / 'q.dproj', 'Empty', 'und')
        app = GlossWebApp(self.tmp.name)
        response = {}
        raw = b''.join(app({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/api/performance', 'HTTP_HOST': '127.0.0.1:8765',
                            'CONTENT_LENGTH': '0', 'wsgi.input': io.BytesIO()}, lambda status, headers: response.update(status=status)))
        self.assertTrue(response['status'].startswith('200'))
        rows = {row['name']: row['performance'] for row in json.loads(raw)}
        self.assertEqual(rows['Velari']['accepted'], 0.5)
        self.assertEqual(rows['Empty']['words'], 0)


class EnglishCorpusTests(unittest.TestCase):
    CONLLU = '\n'.join([
        '# text = The birds chased me.',
        '1\tThe\tthe\tDET\tDT\tDefinite=Def|PronType=Art\t2\tdet\t_\t_',
        '2\tbirds\tbird\tNOUN\tNNS\tNumber=Plur\t3\tnsubj\t_\t_',
        '3\tchased\tchase\tVERB\tVBD\tMood=Ind|Tense=Past|VerbForm=Fin\t0\troot\t_\t_',
        '4\tme\tI\tPRON\tPRP\tCase=Acc|Number=Sing|Person=1|PronType=Prs\t3\tobj\t_\tSpaceAfter=No',
        '5\t.\t.\tPUNCT\t.\t_\t3\tpunct\t_\t_',
        '',
        '# text = She is running in the US.',
        '1\tShe\tshe\tPRON\tPRP\tCase=Nom|Gender=Fem|Number=Sing|Person=3|PronType=Prs\t3\tnsubj\t_\t_',
        '2\tis\tbe\tAUX\tVBZ\tMood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin\t3\taux\t_\t_',
        '3\trunning\trun\tVERB\tVBG\tTense=Pres|VerbForm=Part\t0\troot\t_\t_',
        '4\tin\tin\tADP\tIN\t_\t6\tcase\t_\t_',
        '5\tthe\tthe\tDET\tDT\tDefinite=Def|PronType=Art\t6\tdet\t_\t_',
        '6\tUS\tUS\tPROPN\tNNP\tNumber=Sing\t3\tobl\t_\t_',
        '', ''])

    def test_conllu_becomes_leipzig_style_tsv(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / 'en.conllu', Path(tmp) / 'en.tsv'
            source.write_text(self.CONLLU, encoding='utf-8')
            subprocess.run([sys.executable, '-I', str(ROOT / 'tools' / 'make_english_corpus.py'), '--glossed', str(source),
                            '--review', str(source), '--output', str(output), '--min-words', '3'], check=True, capture_output=True)
            lines = output.read_text(encoding='utf-8').splitlines()
        self.assertEqual(lines, ['The birds chased me\tthe bird-PL chase-PST 1SG.ACC',
                                 'She is running in the US\t3SG be-3SG run-PROG in the us'])
