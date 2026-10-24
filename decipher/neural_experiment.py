"""Development-only, matched online learning experiments and task adapters."""
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import platform
import resource
import statistics
import sys
import time
from .corpus import Analysis, AnnotatedSentence, TextExample, features, read_corpus
from .corpus_learner import CorpusLearner
from .generator import episode
from .learner import RuleLearner
from .meaning import FIELDS
from .neural import NeuralConfig, NeuralLearner
from .online import OnlineSession


@dataclass(frozen=True)
class GoldText:
    id: str
    source: str
    target: str


def meaning_text(meaning):
    return '\t'.join(meaning[field] for field in FIELDS)


def analysis_text(analysis):
    return '\t'.join((analysis.lemma, analysis.upos, '|'.join(analysis.feats) or '_'))


class RuleAdapter:
    def __init__(self, roots, config):
        self.config = config
        self.roots = dict(roots)
        self.learner = RuleLearner(roots)
        self.records = {}
        self.version = 0

    def predict(self, source, **kwargs):
        if source in self.roots:
            value = self.roots[source]
            recall = True
        else:
            prediction = self.learner.predict(source)
            value = meaning_text(prediction['meaning']) if prediction['meaning'] else ''
            recall = prediction['recall']
        return {'text': value, 'candidates': [{'text': value, 'log_score': None}] if value else [], 'recall': recall, 'version': self.version}

    def correct(self, identifier, source, target):
        if self.records.get(identifier) == (source, target):
            return False
        if source not in self.roots:
            values = target.split('\t')
            if len(values) != len(FIELDS):
                raise ValueError('Invalid synthetic target')
            self.learner.correct(source, dict(zip(FIELDS, values)))
        self.records[identifier] = (source, target)
        self.version += 1
        return True


class AffixAdapter:
    def __init__(self, config):
        self.config = config
        self.learner = CorpusLearner()
        self.version = 0

    def predict(self, source, **kwargs):
        tokens = tuple(json.loads(source))
        # Source is [previous word, central word, next word], with sentinels.
        analysis = self.learner.predict(TextExample('input', tokens), verified_memory=False)[1]
        text = analysis_text(analysis) if analysis.lemma is not None else ''
        return {'text': text, 'candidates': [{'text': text, 'log_score': None}] if text else [], 'recall': False, 'version': self.version}

    def correct(self, identifier, source, target):
        values = target.split('\t')
        if len(values) != 3:
            raise ValueError('Invalid morphology target')
        tokens = tuple(json.loads(source))
        unknown = Analysis(None, None, None)
        annotation = (unknown, Analysis(values[0], values[1], features(values[2])), unknown)
        changed = self.learner.correct(TextExample(identifier, tokens), annotation)
        self.version = self.learner.version
        return changed


def synthetic_task(preset, seed, stream_size=60, probe_size=30):
    _, roots, support, stream, probes = episode(preset, seed)
    anchors = [GoldText(f'root-{i}', root, concept) for i, (root, concept) in enumerate(roots.items())]
    convert = lambda group: [GoldText(g.example.id, g.example.source, meaning_text(g.meaning)) for g in group]
    return {'name': f'synthetic-{preset}-{seed}', 'kind': 'synthetic', 'roots': roots,
            'anchors': anchors, 'support': convert(support), 'stream': convert(stream[:stream_size]),
            'probes': convert(probes[:probe_size]), 'prior': '11 declared root anchors; no cross-language pretraining.'}


def corpus_task(train_path, dev_path, support_size=25, stream_size=100, probe_size=100, config=None):
    config = config or NeuralConfig()
    counts = {'training_overlength': 0, 'training_repeated_context': 0, 'probe_overlap': 0, 'probe_overlength': 0}
    def items(path):
        for sentence in read_corpus(path):
            tokens = sentence.example.tokens
            for index, analysis in enumerate(sentence.analyses):
                if analysis.lemma is None or analysis.upos is None or analysis.feats is None:
                    continue
                previous = tokens[index-1] if index else '<BOS>'
                following = tokens[index+1] if index+1<len(tokens) else '<EOS>'
                yield GoldText(f'{sentence.example.id}/{index+1}', json.dumps([previous, tokens[index], following], ensure_ascii=False, separators=(',', ':')), analysis_text(analysis))
    training, seen = [], set()
    for item in items(train_path):
        if len(item.source.encode('utf-8')) > config.max_source_bytes or len(item.target.encode('utf-8')) > config.max_target_bytes:
            counts['training_overlength'] += 1
            continue
        if item.source in seen:
            counts['training_repeated_context'] += 1
            continue
        seen.add(item.source)
        training.append(item)
        if len(training) >= support_size+stream_size:
            break
    probes, seen_probes = [], set()
    for item in items(dev_path):
        if item.source in seen or item.source in seen_probes:
            counts['probe_overlap'] += 1
            continue
        if len(item.source.encode('utf-8')) > config.max_source_bytes or len(item.target.encode('utf-8')) > config.max_target_bytes:
            counts['probe_overlength'] += 1
            continue
        seen_probes.add(item.source)
        probes.append(item)
        if len(probes) >= probe_size:
            break
    if len(training) < support_size+stream_size or len(probes) < probe_size:
        raise ValueError('Corpus is too small for the requested disjoint online task')
    return {'name': Path(train_path).stem, 'kind': 'corpus', 'roots': {}, 'anchors': [],
            'support': training[:support_size], 'stream': training[support_size:], 'probes': probes,
            'prior': 'No pretraining or dictionary; each answer is one lemma/POS/features token annotation; neighboring surface words are supplied.',
            'files': {name: {'path': str(path), 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()} for name, path in [('train',train_path),('development',dev_path)]}, 'filter_counts': counts}


def score(learner, examples, beam_size=1):
    return sum(learner.predict(item.source, beam_size=beam_size)['text'] == item.target for item in examples)/len(examples) if examples else None


def auc(points):
    if len(points)<2 or points[-1]['labels'] == points[0]['labels']:
        return None
    return sum((b['labels']-a['labels'])*(a['accuracy']+b['accuracy'])/2 for a,b in zip(points,points[1:]))/(points[-1]['labels']-points[0]['labels'])


def run(task, mode, config, directory, delay=0, policy='all', probe_every=10):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if mode == 'rules':
        learner = RuleAdapter(task['roots'], config)
    elif mode == 'affix':
        learner = AffixAdapter(config)
    else:
        learner = NeuralLearner(config, mode)
    session = OnlineSession(learner, task['name'])
    for item in task['anchors']+task['support']:
        session.predict(item.id, item.source, beam_size=1)
        session.feedback(item.id, item.target)
    seeds = len(session.processed)
    curves = [{'labels': 0, 'accuracy': score(learner,task['probes'])}]
    retention_set = task['support'][:25]
    retention_curve = [{'labels': 0, 'accuracy': score(learner,retention_set)}]
    decisions, answers, correct = 0, 0, 0
    latencies, updates = [], []
    for i, item in enumerate(task['stream'],1):
        start = time.perf_counter()
        prediction = session.predict(item.id, item.source, beam_size=1)
        latencies.append(time.perf_counter()-start)
        right = prediction['text'] == item.target
        correct += right
        decisions += 1
        if policy == 'all' or not right:
            answers += 1
            start=time.perf_counter()
            session.feedback(item.id,item.target,delay=delay)
            updates.append(time.perf_counter()-start)
        if i % probe_every == 0 or i==len(task['stream']):
            labels=len(session.processed)-seeds
            curves.append({'labels':labels, 'accuracy':score(learner,task['probes'])})
            retention_curve.append({'labels':labels, 'accuracy':score(learner,retention_set)})
    session.export(directory)
    if isinstance(learner,NeuralLearner):
        session.save(directory/'session.pt')
    def latency(values,quantile):
        return sorted(values)[min(len(values)-1,int((len(values)-1)*quantile))]*1000 if values else None
    valid_retention=[p['accuracy'] for p in retention_curve if p['accuracy'] is not None]
    metrics={'mode':mode,'model_seed':config.seed,'delay':delay,'policy':policy,'support_answers':seeds,
             'stream_predictions':len(task['stream']),'stream_accuracy':correct/len(task['stream']),
             'teacher_decisions':decisions,'stream_answers_requested':answers,'stream_answers_arrived':len(session.processed)-seeds,
             'pending_answers':len(session.pending),'pending_drained':False,'curve':curves,'auc':auc(curves),
             'retention_curve':retention_curve,'retention_drop_pp':(max(valid_retention)-valid_retention[-1])*100 if valid_retention else None,
             'optimizer_steps':getattr(learner,'optimizer_steps',0), 'training_examples_consumed':getattr(learner,'training_examples_consumed',0),
             'parameter_count':getattr(learner,'parameter_count',0),
             'prediction_median_ms':latency(latencies,.5),'prediction_p95_ms':latency(latencies,.95),
             'feedback_call_median_ms':latency(updates,.5),'feedback_call_p95_ms':latency(updates,.95)}
    (directory/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
    (directory/'config.json').write_text(json.dumps({'model':asdict(config),'mode':mode,'delay':delay,'policy':policy,'probe_every':probe_every},indent=2)+'\n')
    (directory/'manifest.json').write_text(json.dumps({'task':task['name'],'kind':task['kind'], 'prior':task['prior'], 'support_ids':[x.id for x in task['support']], 'stream_ids':[x.id for x in task['stream']], 'probe_ids':[x.id for x in task['probes']], 'files':task.get('files'), 'filter_counts':task.get('filter_counts')},indent=2)+'\n')
    import torch
    (directory/'environment.json').write_text(json.dumps({'python':sys.version,'torch':torch.__version__,'platform':platform.platform(),'device':getattr(learner,'device','cpu'),'threads':torch.get_num_threads(),'process_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)},indent=2)+'\n')
    print(f"{task['name']} {mode}: probe {curves[0]['accuracy']:.1%} → {curves[-1]['accuracy']:.1%}; first guesses {metrics['stream_accuracy']:.1%}; labels {metrics['stream_answers_arrived']}",flush=True)
    return metrics


def write_experiment_report(rows, directory, protocol):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'results.json').write_text(json.dumps({'protocol':protocol,'runs':rows},indent=2)+'\n')
    lines=['# Online adaptation results','',protocol,'', '| Task | Mode | Seed | Delay | Policy | Final probes | First guesses | AUC | Labels arrived |', '|---|---|---:|---:|---|---:|---:|---:|---:|']
    for row in rows:
        metric=row['metrics']
        area='n/a' if metric['auc'] is None else f"{metric['auc']:.3f}"
        lines.append(f"| {row['task']} | {metric['mode']} | {metric['model_seed']} | {metric['delay']} | {metric['policy']} | {metric['curve'][-1]['accuracy']:.1%} | {metric['stream_accuracy']:.1%} | {area} | {metric['stream_answers_arrived']} |")
    lines += ['', 'No pretrained weights or cross-language initialization. Every neural condition starts from identical seed-specific parameters. Replay sees more training-example presentations per optimizer step; optimizer-step and presentation counts are reported, so these are equal-label comparisons, not equal-compute claims. Exact memory recall and retention are distinct from disjoint probe accuracy. Frozen-mode and tiny-data negative results are reported without selecting the best test outcome. Full state and event logs live in the corresponding local run directories.']
    (directory/'summary.md').write_text('\n'.join(lines)+'\n')
