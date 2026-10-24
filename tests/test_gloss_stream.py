"""Online gloss protocol, private scoring and restart integration regressions."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from decipher.corpus import TextExample
from decipher.gloss import GlossExample
from decipher.gloss_checkpoint import (GlossAdapter, digest, encoded, load_gloss_checkpoint,
                                       save_gloss_checkpoint)
from decipher.gloss_evaluate import (GlossMetrics, annotation_budget, normalized_auc, online_gloss,
                                     reconstruct_metrics, report_gloss, resume_gloss, select_online,
                                     take_snapshot)
from decipher.online import OnlineSession


def tiers(path, rows):
    path.write_text(''.join('\\t '+' '.join(words)+'\n\\g '+' '.join(glosses)+'\n\n'
                            for words, glosses in rows), encoding='utf-8')


def fixtures(directory):
    train, dev = directory/'train', directory/'dev'
    rows = [(('tal', 'mir'), ('tree', 'bird')), (('talum',), ('tree-PL',)),
            (('tal',), ('tree',)), (('mir',), ('bird',))]
    rows += [((f'w{i}',), (f'concept{i}',)) for i in range(22)]
    tiers(train, rows)
    tiers(dev, [(('mirum', '.'), ('bird-PL', '.')), (('new',), ('unknown',))])
    return train, dev


def stable(value):
    """Only physical timing and output locations differ between executions."""
    ignored = {'timestamp', 'latency_ms', 'latency', 'run_directory', 'checkpoint_sha256'}
    if isinstance(value, dict):
        return {key: stable(item) for key, item in value.items() if key not in ignored}
    if isinstance(value, list):
        return [stable(item) for item in value]
    return value


def rewrite_archive(source, destination, name, transform, repair_checksums=True):
    if not zipfile.is_zipfile(source):
        source = source.parent/json.loads(source.read_text(encoding='utf-8'))['checkpoint_file']
    with zipfile.ZipFile(source) as archive:
        files = {key: archive.read(key) for key in archive.namelist()}
    files[name] = transform(files[name])
    if repair_checksums and name != 'integrity.json':
        integrity = json.loads(files['integrity.json'])
        integrity['sha256'][name] = digest(files[name])
        files['integrity.json'] = encoded(integrity)
    with zipfile.ZipFile(destination, 'w') as archive:
        for key, data in files.items():
            archive.writestr(key, data)


class GlossStreamTests(unittest.TestCase):
    def small_run(self, directory, **kwargs):
        train, dev = fixtures(directory)
        report = online_gloss(train, dev, directory/'run', support=1, stream_size=3,
                              delays=(5,), modes=('rules',), probe_every=1, **kwargs)
        return directory/'run'/'rules-delay-5-all'/'checkpoint.json', report

    def test_delay_orders_predictions_before_labels_and_revisions_supersede(self):
        session = OnlineSession(GlossAdapter(), 'fixture')
        first = session.predict('one', '["tal"]')
        self.assertEqual(first['word_predictions'][0]['gloss'], None)
        session.feedback('one', '["tree"]', delay=5)
        self.assertFalse(session.feedback('one', '["tree"]', delay=5))
        session.feedback('one', '["bird"]', delay=2, revision=1)
        self.assertEqual(len(session.pending), 1)
        self.assertEqual(session.learner.learner.records, {})
        before = copy.deepcopy(session.state())
        for target, revision in (('["tree"]', 0), ('["fish"]', 1)):
            with self.assertRaises(ValueError):
                session.feedback('one', target, revision=revision)
        self.assertEqual(session.state(), before)
        session.predict('two', '["mir"]')
        self.assertEqual(session.learner.version, 0)
        session.predict('three', '["vel"]')
        self.assertEqual(session.learner.learner.lexicon['tal'], {'bird': 1})
        self.assertEqual(session.events[0]['prediction'], first)
        session.feedback('one', '["fish"]', revision=2)
        self.assertEqual(session.learner.learner.lexicon['tal'], {'fish': 1})
        self.assertEqual([event['feedback_revision'] for event in session.events if event['event_type'] == 'feedback'], [1, 2])
        self.assertEqual(session.events[0]['prediction'], first)

    def test_invalid_gloss_feedback_cannot_change_queue_or_model(self):
        session = OnlineSession(GlossAdapter())
        session.predict('one', '["tal","mir"]')
        session.feedback('one', '["tree","bird"]', delay=20)
        before = copy.deepcopy(session.state())
        model = copy.deepcopy(session.learner.learner.__dict__)
        for target in ('["tree"]', '["tree",null]', 'not-json', '["two words","bird"]'):
            with self.assertRaises(ValueError):
                session.feedback('one', target, revision=1)
        self.assertEqual(session.state(), before)
        self.assertEqual(session.learner.learner.__dict__, model)

    def test_invalid_source_cannot_advance_time_or_release_pending_answers(self):
        session = OnlineSession(GlossAdapter())
        session.predict('one', '["tal"]')
        session.feedback('one', '["tree"]', delay=1)
        before = copy.deepcopy(session.state())
        for source in ('not-json', '[]', '[null]', '["two words"]'):
            with self.assertRaises(ValueError):
                session.predict('bad', source)
            self.assertEqual(session.state(), before)
            self.assertEqual(session.learner.version, 0)

    def test_all_modes_delays_and_policies_resume_with_identical_histories(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            train, dev = fixtures(directory)
            settings = dict(support=1, stream_size=25, delays=(0, 5, 20),
                            policies=('all', 'corrections'), probe_every=5, checkpoint_every=4)
            full = online_gloss(train, dev, directory/'full', **settings)
            stopped = online_gloss(train, dev, directory/'stopped', max_inputs=7, **settings)
            self.assertEqual(len(full['runs']), 18)
            for expected, partial in zip(full['runs'], stopped['runs']):
                with self.subTest(mode=expected['mode'], delay=expected['delay'], policy=expected['policy']):
                    checkpoint = Path(partial['run_directory'])/'checkpoint.json'
                    historical, experiment = load_gloss_checkpoint(checkpoint)
                    prefix = copy.deepcopy(historical.events)
                    middle = resume_gloss(checkpoint, max_inputs=3, checkpoint_every=2)
                    self.assertEqual(middle['processed_stream_inputs'], 10)
                    actual = resume_gloss(checkpoint)
                    self.assertEqual(encoded(stable(actual)), encoded(stable(expected)))
                    resumed, experiment = load_gloss_checkpoint(checkpoint)
                    uninterrupted, full_experiment = load_gloss_checkpoint(Path(expected['run_directory'])/'checkpoint.json')
                    self.assertEqual(resumed.events[:len(prefix)], prefix)
                    self.assertEqual(encoded(stable(resumed.state())), encoded(stable(uninterrupted.state())))
                    self.assertEqual(resumed.learner.learner.__dict__, uninterrupted.learner.learner.__dict__)
                    self.assertEqual(encoded(experiment['snapshots']), encoded(full_experiment['snapshots']))
                    self.assertTrue(actual['complete'])
                    self.assertFalse(actual['pending_drained'])
                    if expected['policy'] == 'all':
                        self.assertEqual(actual['pending'], expected['delay'])
                        self.assertEqual(actual['budget']['stream']['answers_arrived'], 25-expected['delay'])

    def test_reports_reconstruct_without_new_predictions_or_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            checkpoint, report = self.small_run(directory)
            session, experiment = load_gloss_checkpoint(checkpoint)
            with (patch.object(session.learner.learner, 'predict', side_effect=AssertionError('new prediction')),
                  patch.object(session.learner.learner, 'correct', side_effect=AssertionError('new update'))):
                rebuilt = reconstruct_metrics(session, experiment)
            self.assertEqual(encoded(stable(rebuilt)), encoded(stable(report['runs'][0])))
            exported = report_gloss(checkpoint, directory/'rebuilt.json')
            self.assertEqual(encoded(exported), encoded(rebuilt))
            self.assertEqual(json.loads((checkpoint.parent/'metrics.json').read_text(encoding='utf-8')), rebuilt)

    def test_probes_are_read_only_and_private_answers_never_reach_prediction(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint, _ = self.small_run(Path(tmp), max_inputs=1)
            session, experiment = load_gloss_checkpoint(checkpoint)
            before_model = copy.deepcopy(session.learner.learner.__dict__)
            before_session = copy.deepcopy(session.state())
            seen = []
            original = session.learner.learner.predict
            def public_only(example):
                self.assertIsInstance(example, TextExample)
                self.assertEqual(set(example.__dict__), {'id', 'tokens'})
                seen.append(example)
                return original(example)
            with patch.object(session.learner.learner, 'predict', side_effect=public_only):
                take_snapshot(session, experiment)
            self.assertTrue(seen)
            self.assertEqual(session.learner.learner.__dict__, before_model)
            self.assertEqual(session.state(), before_session)
            for event in session.events:
                if event['event_type'] == 'prediction':
                    self.assertIsInstance(json.loads(event['source']), list)
            self.assertNotIn('mirum', session.learner.learner.lexicon)

    def test_full_candidates_produce_real_top_five_accuracy(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            train, dev = directory/'train', directory/'dev'
            tiers(train, [(('tal', 'x'), ('tree', 'x')), (('tal', 'y'), ('tree-DIM', 'y')),
                          (('tal',), ('tree-DIM',))])
            tiers(dev, [(('new',), ('unknown',))])
            result = online_gloss(train, dev, directory/'run', support=2, stream_size=1,
                                  modes=('memory',), delays=(0,), probe_every=1)['runs'][0]
            self.assertEqual(result['first_predictions']['word_accuracy'], 0)
            self.assertEqual(result['first_predictions']['top5_accuracy'], 1)
        metric = GlossMetrics()
        gold = GlossExample(TextExample('six', ('x',)), ('sixth',))
        metric.add(gold, [{'gloss': 'first', 'known_form': False,
                          'candidates': [{'gloss': str(i)} for i in range(5)]+[{'gloss': 'sixth'}]}])
        self.assertEqual(metric.result()['top5_accuracy'], 0)

    def test_duplicate_sources_are_removed_before_disjoint_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            train, dev = directory/'train', directory/'dev'
            tiers(train, [(('caf\u00e9',), ('coffee',)), (('cafe\u0301',), ('wrong',)),
                          (('b',), ('bee',)), (('c',), ('sea',))])
            tiers(dev, [(('b',), ('bee',)), (('d',), ('dee',)), (('d',), ('other',))])
            roles, filters = select_online(train, dev, 1, 2)
            self.assertEqual([item.example.tokens for item in roles['support']], [('caf\u00e9',)])
            self.assertEqual(filters['training_source_duplicates']['count'], 1)
            self.assertEqual(filters['training_source_duplicates']['conflicting_glosses'], 1)
            self.assertEqual(filters['probe_source_duplicates']['count'], 1)
            self.assertEqual(filters['source_overlaps_excluded'], 1)
            values = [item.example.tokens for items in roles.values() for item in items]
            self.assertEqual(len(values), len(set(values)))

    def test_budgets_count_word_annotations_and_revisions_separately(self):
        session = OnlineSession(GlossAdapter())
        session.predict('seed', '["tal","mir"]')
        session.feedback('seed', '["tree","bird"]')
        session.predict('input', '["talum"]')
        session.events.append(session._event('teacher_decision', example_id='input', requested=True))
        session.feedback('input', '["tree-PL"]')
        session.feedback('input', '["tree-DU"]', revision=1, delay=5)
        scoring = {'support': [{'id': 'seed', 'tokens': ['tal', 'mir']}],
                   'stream': [{'id': 'input', 'tokens': ['talum']}]}
        budget = annotation_budget(session.events, scoring)
        self.assertEqual(budget['support']['words_arrived'], 2)
        self.assertEqual(budget['stream']['answers_requested'], 2)
        self.assertEqual(budget['stream']['answers_arrived'], 1)
        self.assertEqual(budget['stream']['teacher_decisions'], 1)
        self.assertEqual(budget['stream']['revisions_requested'], 1)
        self.assertEqual(budget['stream']['pending_words'], 1)
        self.assertEqual(budget['stream']['unique_annotated_sentences'], 1)

    def test_auc_declares_its_range_and_zero_width_is_undefined(self):
        points = [{'labels': x, 'scores': {'word_accuracy': y}} for x, y in [(0, 0), (0, .2), (5, .6), (10, 1)]]
        result = normalized_auc(points, 'labels')
        self.assertAlmostEqual(result['value'], .6)
        self.assertEqual(result['budget_range'], [0, 10])
        self.assertIsNone(normalized_auc(points[:2], 'labels')['value'])

    def test_checkpoint_rejects_corruption_incomplete_and_inconsistent_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            checkpoint, _ = self.small_run(directory, max_inputs=1)
            bad = directory/'bad.zip'
            bad.write_bytes(checkpoint.read_bytes()[:30])
            with self.assertRaises(ValueError):
                load_gloss_checkpoint(bad)
            with zipfile.ZipFile(bad, 'w') as archive:
                archive.writestr('integrity.json', '{}')
            with self.assertRaises(ValueError):
                load_gloss_checkpoint(bad)
            cases = [('session.json', lambda data: data+b' ', False),
                     ('experiment.json', lambda data: encoded(dict(json.loads(data), cursor=99)), True),
                     ('session.json', lambda data: encoded(dict(json.loads(data), pending=[])), True),
                     ('integrity.json', lambda data: encoded(dict(json.loads(data), schema_version=99)), True),
                     ('experiment.json', lambda data: b'{', True)]
            for name, transform, repair in cases:
                with self.subTest(name=name, repair=repair):
                    rewrite_archive(checkpoint, bad, name, transform, repair)
                    with self.assertRaises(ValueError):
                        load_gloss_checkpoint(bad)

    def test_failed_atomic_save_keeps_previous_complete_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            checkpoint, _ = self.small_run(directory, max_inputs=1)
            before = checkpoint.read_bytes()
            session, experiment = load_gloss_checkpoint(checkpoint)
            original = Path.replace
            def fail_commit(path, target):
                if Path(target) == checkpoint:
                    raise OSError('simulated interrupted commit')
                return original(path, target)
            with patch.object(Path, 'replace', new=fail_commit):
                with self.assertRaises(OSError):
                    save_gloss_checkpoint(checkpoint, session, experiment)
            self.assertEqual(checkpoint.read_bytes(), before)
            load_gloss_checkpoint(checkpoint)
            self.assertEqual([path.name for path in checkpoint.parent.iterdir() if path.is_dir()], ['checkpoints'])

    def test_atomic_save_retries_a_transient_windows_checkpoint_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint, _ = self.small_run(Path(tmp), max_inputs=1)
            session, experiment = load_gloss_checkpoint(checkpoint)
            original, attempts = Path.replace, []
            def transient_lock(path, target):
                if Path(target) == checkpoint:
                    attempts.append(path)
                    if len(attempts) < 3:
                        raise PermissionError('transient Windows sharing violation')
                return original(path, target)
            with patch.object(Path, 'replace', new=transient_lock), patch('decipher.gloss_checkpoint.time.sleep'):
                save_gloss_checkpoint(checkpoint, session, experiment)
            self.assertEqual(len(attempts), 3)
            restored, _ = load_gloss_checkpoint(checkpoint)
            self.assertEqual(restored.state(), session.state())
            before = checkpoint.read_bytes()
            def permanent_lock(path, target):
                if Path(target) == checkpoint:
                    raise PermissionError('persistent sharing violation')
                return original(path, target)
            with (patch.object(Path, 'replace', new=permanent_lock),
                  patch('decipher.gloss_checkpoint.time.sleep') as sleep):
                with self.assertRaises(PermissionError):
                    save_gloss_checkpoint(checkpoint, session, experiment)
            self.assertEqual(sleep.call_count, 5)
            self.assertEqual(checkpoint.read_bytes(), before)
            load_gloss_checkpoint(checkpoint)

    def test_checkpoint_manifest_requires_complete_checksummed_local_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint, _ = self.small_run(Path(tmp), max_inputs=1)
            pointer = json.loads(checkpoint.read_text(encoding='utf-8'))
            standalone = checkpoint.parent/pointer['checkpoint_file']
            original, _ = load_gloss_checkpoint(checkpoint)
            direct, _ = load_gloss_checkpoint(standalone)
            self.assertEqual(original.state(), direct.state())
            bad = checkpoint.parent/'bad-manifest.json'
            for change in ({'checkpoint_file': 'checkpoints/missing.zip'},
                           {'checkpoint_file': '../outside.zip'}, {'schema_version': 99}, {'sha256': '0'*64}):
                with self.subTest(change=change):
                    bad.write_bytes(encoded(dict(pointer, **change)))
                    with self.assertRaises(ValueError):
                        load_gloss_checkpoint(bad)

    def test_revisions_survive_checkpoint_with_original_predictions_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint, _ = self.small_run(Path(tmp), max_inputs=1)
            session, experiment = load_gloss_checkpoint(checkpoint)
            identifier = experiment['scoring']['stream'][0]['id']
            first = copy.deepcopy(session.events)
            session.feedback(identifier, '["tree-DU"]', revision=1)
            session.feedback(identifier, '["tree-PAUC"]', revision=2, delay=2)
            save_gloss_checkpoint(checkpoint, session, experiment)
            resumed, restored = load_gloss_checkpoint(checkpoint)
            self.assertEqual(resumed.events[:len(first)], first)
            self.assertEqual(resumed.pending, session.pending)
            self.assertEqual(resumed.processed, session.processed)
            self.assertEqual(resumed.learner.learner.__dict__, session.learner.learner.__dict__)

    def test_incompatible_inputs_or_implementation_reject_resume_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            checkpoint, _ = self.small_run(directory, max_inputs=1)
            before = checkpoint.read_bytes()
            with patch('decipher.gloss_evaluate.implementation_fingerprint', return_value={'changed': True}):
                with self.assertRaisesRegex(ValueError, 'Implementation changed'):
                    resume_gloss(checkpoint)
            (directory/'train').write_text('changed', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Changed training'):
                resume_gloss(checkpoint)
            self.assertEqual(checkpoint.read_bytes(), before)

    def test_invalid_matrix_options_fail_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            train, dev = fixtures(directory)
            for options in ({'policies': ('bogus',)}, {'delays': ()}, {'delays': (0, 0)},
                            {'support': -1}, {'stream_size': 0}, {'probe_every': 0},
                            {'max_inputs': -1}, {'checkpoint_every': 0}, {'modes': ()}):
                with self.subTest(options=options), self.assertRaises(ValueError):
                    online_gloss(train, dev, directory/'invalid', **options)
                self.assertFalse((directory/'invalid').exists())

    def test_cli_train_stream_resume_and_report_need_only_standard_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            train, dev = fixtures(directory)
            def cli(*arguments):
                return subprocess.run([sys.executable, '-X', 'utf8', '-S', '-m', 'decipher.app', 'gloss', *map(str, arguments)],
                                      capture_output=True, text=True, encoding='utf-8', check=True)
            cli('train', '--train', train, '--model', directory/'model.gz')
            self.assertIn('tree', cli('predict', '--model', directory/'model.gz', '--text', 'tal').stdout)
            cli('stream', '--train', train, '--dev', dev, '--run-dir', directory/'cli', '--support', 1,
                '--stream', 3, '--modes', 'rules', '--delays', 5, '--policies', 'all', '--max-inputs', 1,
                '--probe-every', 1)
            checkpoint = directory/'cli'/'rules-delay-5-all'/'checkpoint.json'
            self.assertIn('complete: True', cli('resume', '--checkpoint', checkpoint).stdout)
            cli('report', '--checkpoint', checkpoint, '--output', directory/'report.json')
            report = json.loads((directory/'report.json').read_text(encoding='utf-8'))
            self.assertEqual(report['processed_stream_inputs'], 3)
            self.assertEqual(report['pending'], 3)
            self.assertTrue(report['complete'])


if __name__ == '__main__':
    unittest.main()
