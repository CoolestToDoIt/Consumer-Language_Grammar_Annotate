"""Offline and prequential source-only gloss evaluation."""
from collections import Counter
from pathlib import Path
import json
import importlib.metadata
import math
import platform
import statistics
import subprocess
import sys
from .corpus import TextExample
from .gloss import GlossExample
from .gloss_checkpoint import (ALGORITHM_ID, SCHEMA_VERSION, GlossAdapter, digest, encoded,
                               implementation_fingerprint, load_gloss_checkpoint,
                               save_gloss_checkpoint)
from .online import OnlineSession
from .gloss import GlossLearner, lexical_key, load_gloss
from .corpus_evaluate import file_info


class GlossMetrics:
    def __init__(self):
        self.counts=Counter()
        self.errors=[]

    def add(self,gold,predictions,model=None,grounded_lexemes=()):
        if len(gold.glosses)!=len(predictions):
            raise ValueError('Predictions must align with gold word glosses')
        c=self.counts
        c['sentences']+=1
        right_sentence=True
        grounded=set(model.paradigms) if model is not None else {tuple(key) for key in grounded_lexemes}
        for word,target,prediction in zip(gold.example.tokens,gold.glosses,predictions):
            correct=prediction['gloss']==target
            oov=word not in model.lexicon if model is not None else not prediction['known_form']
            c['words']+=1
            c['correct']+=correct
            c['covered']+=prediction['gloss'] is not None
            c['top5_correct']+=any(candidate['gloss']==target for candidate in prediction['candidates'][:5])
            if any(char.isalnum() for char in word):
                c['nonpunct_words']+=1
                c['nonpunct_correct']+=correct
            if oov:
                c['oov_words']+=1
                c['oov_correct']+=correct
                key=lexical_key(target)
                label='grounded_oov' if key and key in grounded else 'ungrounded_or_grammatical_oov'
                c[label+'_words']+=1
                c[label+'_correct']+=correct
            right_sentence &= correct
            if not correct and len(self.errors)<25:
                self.errors.append({'id':gold.example.id,'source_word':word,'expected':target,'predicted':prediction['gloss'],'oov':oov})
        c['correct_sentences']+=right_sentence

    def result(self):
        c=self.counts
        def ratio(a,b):
            return c[a]/c[b] if c[b] else None
        return {'counts':dict(c),'word_accuracy':ratio('correct','words'),'sentence_accuracy':ratio('correct_sentences','sentences'),
                'coverage':ratio('covered','words'),'top5_accuracy':ratio('top5_correct','words'),'oov_accuracy':ratio('oov_correct','oov_words'),
                'nonpunct_accuracy':ratio('nonpunct_correct','nonpunct_words'), 'grounded_oov_accuracy':ratio('grounded_oov_correct','grounded_oov_words'),
                'errors':self.errors}


def prepare(train_path,eval_path):
    training,train_stats=load_gloss(train_path,skip_misaligned=True)
    evaluation,eval_stats=load_gloss(eval_path,skip_misaligned=True)
    sources={item.example.tokens for item in training}
    probes=[item for item in evaluation if item.example.tokens not in sources]
    if not training or not probes:
        raise ValueError('Need nonempty training and nonoverlapping evaluation sets')
    return training,probes,{'training_reader':train_stats,'evaluation_reader':eval_stats,
                           'source_overlaps_excluded':len(evaluation)-len(probes),
                           'source_overlap_ids_excluded':[item.example.id for item in evaluation if item.example.tokens in sources]}


def evaluate_gloss(train_path,eval_path,output,split='dev',max_rules=512):
    if split not in ('dev','test'):
        raise ValueError('split must be dev or test')
    training,probes,filters=prepare(train_path,eval_path)
    models={name:GlossLearner(name,max_rules) for name in ('memory','analogy','rules')}
    for model in models.values():
        model.fit(training)
    results={}
    for name,model in models.items():
        metric=GlossMetrics()
        for gold in probes:
            metric.add(gold,model.predict(gold.example),model)
        results[name]={**metric.result(),'rules_considered':len(model._rules())}
    report={'task':'Word-aligned, source-only interlinear gloss prediction; no translations or gold segmentation as input.',
            'split':split,'training':file_info(train_path),'evaluation':file_info(eval_path),'filters':filters,
            'training_sentences':len(training),'training_words':sum(len(g.example.tokens) for g in training),
            'config':{'max_rules':max_rules,'paradigm_window':32,'source_only':True,'gold_segmentation':False,'translation_input':False},'models':results}
    manifest = {'schema_version': SCHEMA_VERSION, 'algorithm_id': 'source-only-gloss-offline-v1',
                'training': report['training'], 'evaluation': report['evaluation'], 'split': split,
                'config': report['config'], 'filters': filters, 'provenance': provenance(),
                'selections': {'training': [public_record(item) for item in training],
                               'probes': [public_record(item) for item in probes]},
                'duplicate_policy': 'Offline training preserves annotated records; training-source overlaps excluded from probes.'}
    report['manifest_sha256'] = digest(encoded(manifest))
    destination=Path(output)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write_json(destination.with_suffix('.manifest.json'), manifest)
    lines=['# Source-only real-language glossing','',report['task'],'',f"Training sentences: {len(training)}; words: {report['training_words']}. Split: {split}. Excluded sentence-source overlaps: {filters['source_overlaps_excluded']}.",'',
           '| Model | Word exact | OOV word | Grounded lexical OOV | Nonpunctuation word | Sentence exact | Top 5 |','|---|---:|---:|---:|---:|---:|---:|']
    for name,result in results.items():
        def pct(value):
            return 'n/a' if value is None else f'{value:.1%}'
        lines.append('| '+name+' | '+' | '.join(pct(result[key]) for key in ('word_accuracy','oov_accuracy','grounded_oov_accuracy','nonpunct_accuracy','sentence_accuracy','top5_accuracy'))+' |')
    lines += ['', 'Inputs contain only whitespace-delimited source words. Translation, morphological-segmentation and POS tiers are discarded by the reader. This is a stricter source-only variant of shared-task track 1, not a directly comparable official shared-task score. The pinned data_v2 split differs from the original 2023 release.', '',
              'Rules learn prefix/suffix substitutions within a teacher-grounded lexical paradigm and transfer them to another grounded form. The lexical-paradigm heuristic uses lowercase lexical gloss labels and uppercase grammar conventions; this is a declared linguistic assumption. Rule scores are uncalibrated. Unsupported roots remain unknown. Grounded-OOV diagnostics use lexical labels privately in the scorer; they are never a model input. All denominators and alignment exclusions are in JSON.']
    destination.with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for name,result in results.items():
        print(f"{name}: {result['word_accuracy']:.1%} word exact; OOV {result['oov_accuracy'] if result['oov_accuracy'] is not None else 'n/a'}")
    return report


def write_json(path, value):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def gold_record(item):
    return {'id': item.example.id, 'tokens': list(item.example.tokens), 'glosses': list(item.glosses)}


def gold_from_record(row):
    return GlossExample(TextExample(row['id'], tuple(row['tokens'])), tuple(row['glosses']))


def public_record(item):
    return {'id': item.example.id, 'tokens': list(item.example.tokens),
            'source_sha256': digest(encoded(item.example.tokens))}


def select_online(train_path, dev_path, support, stream_size):
    training, probes, filters = prepare(train_path, dev_path)
    def unique(records):
        seen, selected, excluded, conflicts = {}, [], [], 0
        for item in records:
            if item.example.tokens in seen:
                excluded.append(item.example.id)
                conflicts += item.glosses != seen[item.example.tokens].glosses
            else:
                seen[item.example.tokens] = item
                selected.append(item)
        return selected, {'count': len(excluded), 'ids': excluded, 'conflicting_glosses': conflicts}
    training, filters['training_source_duplicates'] = unique(training)
    probes, filters['probe_source_duplicates'] = unique(probes)
    if len(training) < support+stream_size:
        raise ValueError('Not enough unique aligned training sources for the support/stream budget')
    roles = {'support': training[:support], 'stream': training[support:support+stream_size], 'probes': probes}
    identifiers = [item.example.id for values in roles.values() for item in values]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError('Support/stream/probe IDs must be disjoint')
    return roles, filters


def provenance():
    root = Path(__file__).resolve().parents[1]
    def git(*arguments):
        try:
            result = subprocess.run(['git', *arguments], cwd=root, capture_output=True, text=True,
                                    encoding='utf-8', timeout=5, check=True)
            return result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    try:
        torch_version = importlib.metadata.version('torch')
    except importlib.metadata.PackageNotFoundError:
        torch_version = None
    return {'source_commit': git('rev-parse', 'HEAD'), 'branch': git('branch', '--show-current'),
            'working_tree_status': git('status', '--short'), 'implementation_sha256': implementation_fingerprint(),
            'environment': {'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(),
                            'machine': platform.machine(), 'processor': platform.processor(),
                            'torch_installed_version': torch_version, 'torch_required': False}}


def make_experiment(train_path, dev_path, roles, filters, config, origin=None):
    manifest = {'schema_version': SCHEMA_VERSION, 'algorithm_id': ALGORITHM_ID,
                'selection': 'First unique aligned training sources in upstream order; prefix experiment.',
                'training': file_info(Path(train_path).resolve()), 'evaluation': file_info(Path(dev_path).resolve()),
                'filters': filters, 'config': config,
                'selections': {role: [public_record(item) for item in items] for role, items in roles.items()},
                'scoring_sha256': digest(encoded({role: [gold_record(item) for item in items] for role, items in roles.items()})),
                'provenance': origin if origin is not None else provenance(),
                'source_only': True, 'translation_input': False, 'gold_segmentation_input': False,
                'scores_are_probabilities': False, 'pending_drained': False}
    return {'schema_version': SCHEMA_VERSION, 'manifest': manifest, 'cursor': 0, 'snapshots': [],
            'scoring': {role: [gold_record(item) for item in items] for role, items in roles.items()}}


def annotation_budget(events, scoring):
    """Counts are derived from immutable events, including superseded revisions."""
    role_of = {row['id']: role for role in ('support', 'stream') for row in scoring[role]}
    lengths = {row['id']: len(row['tokens']) for role in ('support', 'stream') for row in scoring[role]}
    result = {role: dict.fromkeys(('processed_inputs', 'teacher_decisions', 'answers_requested',
                                  'words_requested', 'answers_arrived', 'words_arrived',
                                  'revisions_requested', 'revisions_arrived', 'pending_answers',
                                  'pending_words', 'superseded_pending_answers', 'superseded_pending_words',
                                  'unique_annotated_sentences', 'unique_annotated_words'), 0)
              for role in ('support', 'stream')}
    pending, processed = {}, {}
    for event in events:
        identifier = event.get('example_id')
        if identifier not in role_of:
            continue
        counts, size = result[role_of[identifier]], lengths[identifier]
        kind = event['event_type']
        if kind == 'prediction':
            counts['processed_inputs'] += 1
        elif kind == 'teacher_decision':
            counts['teacher_decisions'] += 1
        elif kind == 'feedback_requested':
            counts['answers_requested'] += 1
            counts['words_requested'] += size
            counts['revisions_requested'] += event['feedback_revision'] > 0
            if identifier in pending:
                counts['superseded_pending_answers'] += 1
                counts['superseded_pending_words'] += size
            pending[identifier] = event
        elif kind == 'feedback':
            counts['answers_arrived'] += 1
            counts['words_arrived'] += size
            counts['revisions_arrived'] += event['feedback_revision'] > 0
            pending.pop(identifier, None)
            processed[identifier] = event
    for identifier in pending:
        result[role_of[identifier]]['pending_answers'] += 1
        result[role_of[identifier]]['pending_words'] += lengths[identifier]
    for identifier in processed:
        result[role_of[identifier]]['unique_annotated_sentences'] += 1
        result[role_of[identifier]]['unique_annotated_words'] += lengths[identifier]
    return result


def take_snapshot(session, experiment):
    learner = session.learner.learner
    def predictions(rows):
        return [{'id': row['id'], 'words': learner.predict(TextExample(row['id'], tuple(row['tokens'])))} for row in rows]
    recall = [gold_record(item) for item in learner.records.values()]
    experiment['snapshots'].append({'processed_stream_inputs': experiment['cursor'],
                                    'event_count': len(session.events), 'model_version': learner.version,
                                    'grounded_lexemes': [list(key) for key in sorted(learner.paradigms)],
                                    'probes': predictions(experiment['scoring']['probes']),
                                    'retention': predictions(experiment['scoring']['support']),
                                    'recall_gold': recall, 'recall': predictions(recall)})


def normalized_auc(points, budget_key):
    # Repeated answer counts do not add area. The last snapshot at that budget wins.
    values = {point[budget_key]: point['scores']['word_accuracy'] for point in points}
    values = sorted((x, y) for x, y in values.items() if y is not None)
    start, end = (values[0][0], values[-1][0]) if values else (None, None)
    width = end-start if values else 0
    area = sum((xb-xa)*(ya+yb)/2 for (xa, ya), (xb, yb) in zip(values, values[1:]))
    return {'value': area/width if width else None, 'budget_key': budget_key,
            'budget_range': [start, end], 'unique_points': len(values), 'integration': 'trapezoidal, sampled snapshots'}


def reconstruct_metrics(session, experiment):
    """No prediction or learning calls: original logs and private gold suffice."""
    scoring, manifest = experiment['scoring'], experiment['manifest']
    stream_gold = {row['id']: gold_from_record(row) for row in scoring['stream']}
    first = GlossMetrics()
    for event in session.events:
        if event['event_type'] == 'prediction' and event['example_id'] in stream_gold:
            prediction = event['prediction']
            first.add(stream_gold[event['example_id']], prediction['word_predictions'],
                      grounded_lexemes=prediction['grounded_lexemes'])
    curve = []
    for snapshot in experiment['snapshots']:
        def score(key, rows):
            targets = {row['id']: gold_from_record(row) for row in rows}
            metric = GlossMetrics()
            for row in snapshot[key]:
                metric.add(targets[row['id']], row['words'], grounded_lexemes=snapshot['grounded_lexemes'])
            return metric.result()
        budget = annotation_budget(session.events[:snapshot['event_count']], scoring)
        curve.append({'processed_stream_inputs': snapshot['processed_stream_inputs'],
                      'model_version': snapshot['model_version'], 'budget': budget,
                      'arrived_sentence_labels': budget['stream']['answers_arrived'],
                      'arrived_word_labels': budget['stream']['words_arrived'],
                      'scores': score('probes', scoring['probes']),
                      'support_retention': score('retention', scoring['support']),
                      'training_recall': score('recall', snapshot['recall_gold'])})
    retention = [point['support_retention']['word_accuracy'] for point in curve
                 if point['support_retention']['word_accuracy'] is not None]
    def latency(kind):
        values = sorted(event['latency_ms'] for event in session.events if event['event_type'] == kind)
        return {'count': len(values), 'median_ms': statistics.median(values) if values else None,
                'p95_ms': values[max(0, math.ceil(len(values)*.95)-1)] if values else None}
    budget = annotation_budget(session.events, scoring)
    return {**manifest['config'], 'manifest_sha256': digest(encoded(manifest)), 'curve': curve,
            'complete': experiment['cursor'] == len(scoring['stream']), 'prefix_experiment': True,
            'processed_stream_inputs': experiment['cursor'], 'first_predictions': first.result(),
            'budget': budget, 'teacher_decisions': budget['stream']['teacher_decisions'],
            'pending': len(session.pending), 'pending_drained': False,
            'auc_sentences': normalized_auc(curve, 'arrived_sentence_labels'),
            'auc_words': normalized_auc(curve, 'arrived_word_labels'),
            'retention_drop_pp': (max(retention)-retention[-1])*100 if retention else None,
            'latency': {'prediction': latency('prediction'), 'feedback_application': latency('feedback')},
            'latency_scope': 'All support/stream model calls; excludes probes, I/O, checkpoint validation and due-feedback time from prediction.'}


def validate_experiment(experiment, session):
    manifest, scoring = experiment['manifest'], experiment['scoring']
    config = manifest['config']
    if manifest.get('schema_version') != SCHEMA_VERSION or manifest.get('algorithm_id') != ALGORITHM_ID:
        raise ValueError('Unsupported experiment manifest')
    _validate_config(config['support'], config['stream_size'], (config['delay'],), (config['policy'],),
                     config['probe_every'], (config['mode'],), config['max_rules'], config['paradigm_window'])
    cursor = experiment['cursor']
    if type(cursor) is not int or not 0 <= cursor <= config['stream_size']:
        raise ValueError('Invalid remaining-stream cursor')
    if set(scoring) != {'support', 'stream', 'probes'} or digest(encoded(scoring)) != manifest['scoring_sha256']:
        raise ValueError('Private scoring data does not match its frozen manifest')
    ids, sources = [], []
    for role in ('support', 'stream', 'probes'):
        public = []
        for row in scoring[role]:
            item = gold_from_record(row)
            # Reuse the adapter's alignment and label validation without learning.
            session.learner.validate_feedback(encoded(item.example.tokens).decode('utf-8'), encoded(item.glosses).decode('utf-8'))
            if not isinstance(item.example.id, str) or not item.example.id:
                raise ValueError('Invalid selected ID')
            ids.append(item.example.id)
            sources.append(item.example.tokens)
            public.append(public_record(item))
        if public != manifest['selections'][role]:
            raise ValueError('Selected IDs/source order differs from manifest')
    if len(ids) != len(set(ids)) or len(sources) != len(set(sources)):
        raise ValueError('Support/stream/probes must have disjoint IDs and whole sources')
    if len(scoring['support']) != config['support'] or len(scoring['stream']) != config['stream_size'] or not scoring['probes']:
        raise ValueError('Selected sentence budgets do not match configuration')
    expected = scoring['support']+scoring['stream'][:cursor]
    prediction_ids = [event['example_id'] for event in session.events if event['event_type'] == 'prediction']
    if prediction_ids != [row['id'] for row in expected] or any(
            session.sources[row['id']] != json.dumps(row['tokens'], ensure_ascii=False, separators=(',', ':')) for row in expected):
        raise ValueError('Processed sources do not match the frozen stream prefix')
    learner = session.learner.learner
    if (learner.mode, learner.max_rules, learner.paradigm_window) != (config['mode'], config['max_rules'], config['paradigm_window']):
        raise ValueError('Checkpoint model configuration differs from manifest')
    decisions = [event for event in session.events if event['event_type'] == 'teacher_decision']
    if [event['example_id'] for event in decisions] != [row['id'] for row in scoring['stream'][:cursor]]:
        raise ValueError('Teacher decisions do not match processed inputs')
    predictions = {event['example_id']: event['prediction'] for event in session.events if event['event_type'] == 'prediction'}
    for event, row in zip(decisions, scoring['stream']):
        requested = config['policy'] == 'all' or json.loads(predictions[row['id']]['text']) != row['glosses']
        if event['requested'] != requested:
            raise ValueError('Teacher decision differs from the saved first prediction/policy')
    targets = {row['id']: row for row in expected}
    support_ids = {row['id'] for row in scoring['support']}
    requested_ids = support_ids | {event['example_id'] for event in decisions if event['requested']}
    original_requests = [event for event in session.events if event['event_type'] == 'feedback_requested'
                         and event['feedback_revision'] == 0]
    if len(original_requests) != len(requested_ids) or {event['example_id'] for event in original_requests} != requested_ids:
        raise ValueError('Requested answers do not match the teacher decisions')
    for event in original_requests:
        delay = 0 if event['example_id'] in support_ids else config['delay']
        if (json.loads(event['target']) != targets[event['example_id']]['glosses']
                or event['arrival_step'] != event['step']+delay):
            raise ValueError('Requested answer/delay differs from the frozen experiment')
    expected_points = [0]+[i for i in range(1, cursor+1) if i % config['probe_every'] == 0 or i == config['stream_size']]
    snapshots = experiment['snapshots']
    if [point['processed_stream_inputs'] for point in snapshots] != expected_points:
        raise ValueError('Missing, duplicated or incompatible fixed probe snapshots')
    for point in snapshots:
        count = point['event_count']
        if type(count) is not int or not 0 <= count <= len(session.events):
            raise ValueError('Invalid probe event boundary')
        budget = annotation_budget(session.events[:count], scoring)
        if budget['stream']['processed_inputs'] != point['processed_stream_inputs']:
            raise ValueError('Probe snapshot cursor disagrees with history')
        authoritative = {}
        version = 0
        for event in session.events[:count]:
            if event['event_type'] == 'feedback':
                identifier = event['example_id']
                if event['changed']:
                    authoritative.pop(identifier, None)
                authoritative[identifier] = {'id': identifier, 'tokens': json.loads(session.sources[identifier]),
                                             'glosses': json.loads(event['target'])}
                version = event['model_version']
        grounded = {lexical_key(gloss) for row in authoritative.values() for gloss in row['glosses'] if lexical_key(gloss)}
        if (point['model_version'] != version or point['recall_gold'] != list(authoritative.values())
                or point['grounded_lexemes'] != [list(key) for key in sorted(grounded)]):
            raise ValueError('Probe snapshot model version or authoritative scoring state is inconsistent')
        for key, role in (('probes', 'probes'), ('retention', 'support')):
            if [row['id'] for row in point[key]] != [row['id'] for row in scoring[role]]:
                raise ValueError('Probe/retention selection changed within the run')
    # Validate all saved prediction alignments and metric fields before continuation.
    reconstruct_metrics(session, experiment)


def _validate_config(support, stream_size, delays, policies, probe_every, modes, max_rules, paradigm_window):
    if (type(support) is not int or support < 0 or type(stream_size) is not int or stream_size < 1
            or type(probe_every) is not int or probe_every < 1 or type(max_rules) is not int or max_rules < 1
            or type(paradigm_window) is not int or paradigm_window < 1
            or not delays or any(type(delay) is not int or delay < 0 for delay in delays)
            or not policies or any(policy not in ('all', 'corrections') for policy in policies)
            or not modes or any(mode not in ('memory', 'analogy', 'rules') for mode in modes)
            or any(len(values) != len(set(values)) for values in (delays, policies, modes))):
        raise ValueError('Invalid or duplicated stream configuration')


def _validate_limits(max_inputs, checkpoint_every):
    if max_inputs is not None and (type(max_inputs) is not int or max_inputs < 0):
        raise ValueError('max_inputs must be a nonnegative additional input budget')
    if type(checkpoint_every) is not int or checkpoint_every < 1:
        raise ValueError('checkpoint_every must be a positive integer')


def _advance(session, experiment, directory, max_inputs=None, checkpoint_every=25):
    _validate_limits(max_inputs, checkpoint_every)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    config, stream = experiment['manifest']['config'], experiment['scoring']['stream']
    end = len(stream) if max_inputs is None else min(len(stream), experiment['cursor']+max_inputs)
    while experiment['cursor'] < end:
        row = stream[experiment['cursor']]
        prediction = session.predict(row['id'], json.dumps(row['tokens'], ensure_ascii=False, separators=(',', ':')))
        # Private teacher/scorer access occurs only after the original prediction is saved.
        requested = config['policy'] == 'all' or json.loads(prediction['text']) != row['glosses']
        session.events.append(session._event('teacher_decision', example_id=row['id'], requested=requested))
        if requested:
            session.feedback(row['id'], json.dumps(row['glosses'], ensure_ascii=False, separators=(',', ':')), delay=config['delay'])
        experiment['cursor'] += 1
        if experiment['cursor'] % config['probe_every'] == 0 or experiment['cursor'] == len(stream):
            take_snapshot(session, experiment)
        if experiment['cursor'] % checkpoint_every == 0:
            save_gloss_checkpoint(directory/'checkpoint.zip', session, experiment)
    save_gloss_checkpoint(directory/'checkpoint.zip', session, experiment)
    session.export(directory)
    session.learner.learner.save(directory/'model.json.gz')
    write_json(directory/'manifest.json', experiment['manifest'])
    write_json(directory/'scoring.json', experiment['scoring'])
    (directory/'probes.jsonl').write_text(''.join(encoded(point).decode('utf-8')+'\n' for point in experiment['snapshots']), encoding='utf-8')
    row = reconstruct_metrics(session, experiment)
    write_json(directory/'metrics.json', row)
    return row


def write_online_report(report, directory):
    directory = Path(directory)
    write_json(directory/'results.json', report)
    def percent(value):
        return 'n/a' if value is None else f'{value:.2%}'
    lines = ['# Source-only gloss online development results', '', report['task'], '',
             '| Mode | Delay | Policy | Inputs | Labels arrived (sentences / words) | Pending | First word | Final probe word | Sentence AUC |',
             '|---|---:|---|---:|---:|---:|---:|---:|---:|']
    for row in report['runs']:
        budget = row['budget']['stream']
        lines.append(f"| {row['mode']} | {row['delay']} | {row['policy']} | {row['processed_stream_inputs']} | "
                     f"{budget['answers_arrived']} / {budget['words_arrived']} | {row['pending']} | "
                     f"{percent(row['first_predictions']['word_accuracy'])} | {percent(row['curve'][-1]['scores']['word_accuracy'])} | "
                     f"{percent(row['auc_sentences']['value'])} |")
    lines += ['', 'These are prefix development experiments in upstream order, not full-corpus or final-language results. '
              'Whole-source duplicates are removed before selection; the first annotation is kept and conflicts are counted. '
              'Fixed development probes exclude every aligned training source, not just the selected prefix.', '',
              'All-label runs share supervision schedules. Correction-only runs request labels according to their own saved errors, '
              'so their answer exposure can differ. Compare both processed inputs and arrived sentence/word labels. '
              'Support labels are reported separately and excluded from the curve x-axis. AUC is trapezoidal over the recorded '
              'probe snapshots and normalized over each run\'s declared arrived-answer range; different ranges require care in comparisons.', '',
              'First predictions, held-out transfer, fixed support retention and current training recall are separate measurements. '
              'Full top-five candidates are saved. Scores are uncalibrated. Pending labels are not drained. '
              'Latency reports give median/p95 model-call milliseconds; checkpoint, report and probe costs are excluded. '
              'No language-level significance or unrestricted translation claim is made.', '']
    (directory/'summary.md').write_text('\n'.join(lines), encoding='utf-8')


def online_gloss(train_path, dev_path, directory, support=10, stream_size=100, delays=(0, 5, 20),
                 policies=('all',), probe_every=25, modes=('memory', 'analogy', 'rules'),
                 max_rules=512, paradigm_window=32, max_inputs=None, checkpoint_every=25, report_dir=None):
    _validate_config(support, stream_size, delays, policies, probe_every, modes, max_rules, paradigm_window)
    _validate_limits(max_inputs, checkpoint_every)
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError(f'Refusing to overwrite an experiment: {directory}; use resume for an existing checkpoint')
    if report_dir is not None and Path(report_dir).exists() and any(Path(report_dir).iterdir()):
        raise ValueError(f'Refusing to overwrite a report: {report_dir}')
    roles, filters = select_online(train_path, dev_path, support, stream_size)
    origin = provenance()
    rows = []
    for mode in modes:
        for delay in delays:
            for policy in policies:
                run_directory = directory/f'{mode}-delay-{delay}-{policy}'
                config = {'mode': mode, 'delay': delay, 'policy': policy, 'support': support,
                          'stream_size': stream_size, 'probe_every': probe_every,
                          'max_rules': max_rules, 'paradigm_window': paradigm_window}
                experiment = make_experiment(train_path, dev_path, roles, filters, config, origin)
                session = OnlineSession(GlossAdapter(mode, max_rules, paradigm_window), Path(train_path).stem)
                for item in roles['support']:
                    session.predict(item.example.id, json.dumps(item.example.tokens, ensure_ascii=False, separators=(',', ':')))
                    session.feedback(item.example.id, json.dumps(item.glosses, ensure_ascii=False, separators=(',', ':')))
                take_snapshot(session, experiment)
                row = _advance(session, experiment, run_directory, max_inputs, checkpoint_every)
                row['run_directory'] = str(run_directory)
                row['checkpoint_sha256'] = digest((run_directory/'checkpoint.zip').read_bytes())
                rows.append(row)
                print(f"{mode}, delay {delay}, {policy}: {row['processed_stream_inputs']} inputs; "
                      f"{row['budget']['stream']['answers_arrived']} arrived answers; "
                      f"probe {row['curve'][-1]['scores']['word_accuracy']:.2%}", flush=True)
    report = {'schema_version': SCHEMA_VERSION,
              'task': 'Source-only real glossing; prediction before correction; fixed disjoint development probes.',
              'support_sentences': support, 'support_words': sum(len(item.example.tokens) for item in roles['support']),
              'stream_sentences': stream_size, 'stream_words': sum(len(item.example.tokens) for item in roles['stream']),
              'probe_sentences': len(roles['probes']), 'probe_words': sum(len(item.example.tokens) for item in roles['probes']),
              'training': file_info(train_path), 'evaluation': file_info(dev_path), 'filters': filters,
              'provenance': origin, 'runs': rows}
    write_online_report(report, directory)
    if report_dir is not None:
        write_online_report(report, report_dir)
    return report


def resume_gloss(checkpoint, directory=None, max_inputs=None, checkpoint_every=25):
    _validate_limits(max_inputs, checkpoint_every)
    session, experiment = load_gloss_checkpoint(checkpoint)
    manifest = experiment['manifest']
    if manifest['provenance']['implementation_sha256'] != implementation_fingerprint():
        raise ValueError('Implementation changed since this experiment; resume with the recorded source revision')
    for key in ('training', 'evaluation'):
        if file_info(manifest[key]['path'])['sha256'] != manifest[key]['sha256']:
            raise ValueError(f'Changed {key} dataset; refusing incompatible resume')
    destination = Path(directory) if directory is not None else Path(checkpoint).parent
    if destination.resolve() != Path(checkpoint).parent.resolve() and destination.exists() and any(destination.iterdir()):
        raise ValueError('Resume output must be the original run directory or an empty new directory')
    return _advance(session, experiment, destination, max_inputs, checkpoint_every)


def report_gloss(checkpoint, output):
    session, experiment = load_gloss_checkpoint(checkpoint)
    result = reconstruct_metrics(session, experiment)
    write_json(output, result)
    return result
