"""Frozen corpus evaluation: model inputs contain tokens, never labels."""
from collections import Counter
import hashlib
from itertools import islice
import json
from pathlib import Path
from time import perf_counter
import platform
import sys
from .corpus import read_corpus
from .corpus_learner import CorpusLearner, ALGORITHM_ID


def file_info(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''):
            digest.update(chunk)
    return {'path': str(path), 'sha256': digest.hexdigest()}


class Metrics:
    def __init__(self):
        self.counts = Counter()
        self.features = Counter()

    def add(self, gold, predictions, known_forms):
        if len(gold.analyses) != len(predictions):
            raise ValueError('Prediction/annotation token counts differ')
        sentence_correct = True
        sentence_complete = True
        self.counts['sentences'] += 1
        for word, expected, predicted in zip(gold.example.tokens, gold.analyses, predictions):
            oov = word not in known_forms
            self.counts['tokens'] += 1
            self.counts['oov_tokens'] += oov
            self.counts['covered_tokens'] += predicted.upos is not None
            complete = all(getattr(expected, field) is not None for field in ('lemma', 'upos', 'feats'))
            correct = predicted == expected
            if complete:
                self.counts['joint_total'] += 1
                self.counts['joint_correct'] += correct
                if oov:
                    self.counts['oov_joint_total'] += 1
                    self.counts['oov_joint_correct'] += correct
                if expected.upos != 'PUNCT':
                    self.counts['nonpunct_joint_total'] += 1
                    self.counts['nonpunct_joint_correct'] += correct
            for field in ('lemma', 'upos', 'feats'):
                if getattr(expected, field) is not None:
                    self.counts[field + '_total'] += 1
                    self.counts[field + '_correct'] += getattr(predicted, field) == getattr(expected, field)
                    if oov:
                        self.counts['oov_' + field + '_total'] += 1
                        self.counts['oov_' + field + '_correct'] += getattr(predicted, field) == getattr(expected, field)
            if expected.feats is not None:
                gold_features = set(expected.feats)
                predicted_features = set(predicted.feats or ())
                self.features['tp'] += len(gold_features & predicted_features)
                self.features['fp'] += len(predicted_features - gold_features)
                self.features['fn'] += len(gold_features - predicted_features)
            sentence_complete &= complete
            sentence_correct &= correct
        if sentence_complete:
            self.counts['sentence_total'] += 1
            self.counts['sentence_correct'] += sentence_correct

    def result(self):
        c = self.counts
        def ratio(numerator, denominator):
            return c[numerator]/c[denominator] if c[denominator] else None
        result = {'counts': dict(c), 'coverage': ratio('covered_tokens', 'tokens'),
                  'joint_accuracy': ratio('joint_correct', 'joint_total'),
                  'seen_joint_accuracy': ((c['joint_correct']-c['oov_joint_correct'])/(c['joint_total']-c['oov_joint_total'])) if c['joint_total'] != c['oov_joint_total'] else None,
                  'nonpunct_joint_accuracy': ratio('nonpunct_joint_correct', 'nonpunct_joint_total'),
                  'sentence_exact_accuracy': ratio('sentence_correct', 'sentence_total'),
                  'oov_joint_accuracy': ratio('oov_joint_correct', 'oov_joint_total')}
        for field in ('lemma', 'upos', 'feats'):
            result[field + '_accuracy'] = ratio(field+'_correct', field+'_total')
            result['oov_'+field+'_accuracy'] = ratio('oov_'+field+'_correct', 'oov_'+field+'_total')
        tp, fp, fn = (self.features[name] for name in ('tp', 'fp', 'fn'))
        result['feature_micro_f1'] = 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None
        result['feature_counts'] = dict(self.features)
        return result


def train(path, model='affix', limit=None):
    learner = CorpusLearner(model)
    start = perf_counter()
    for gold in islice(read_corpus(path), limit):
        learner.correct(gold.example, gold.analyses)
    if not learner.token_count:
        raise ValueError('Training corpus contains no fully annotated tokens')
    return learner, perf_counter()-start


def evaluate_corpus(train_path, eval_path, output, split='dev', model_path=None, limit_train=None, limit_eval=None, models=('lexicon', 'affix')):
    if split not in ('dev', 'test'):
        raise ValueError('Evaluation split must be dev or test')
    learner, train_seconds = train(train_path, limit=limit_train)
    training_sources = {record.example.tokens for record in learner.records.values()}
    metrics = {model: Metrics() for model in models}
    elapsed = Counter()
    excluded, read_count, scored_count = 0, 0, 0
    errors = {model: [] for model in models}
    for gold in islice(read_corpus(eval_path), limit_eval):
        read_count += 1
        if gold.example.tokens in training_sources:
            excluded += 1
            continue
        scored_count += 1
        for model in models:
            start = perf_counter()
            predictions = learner.predict(gold.example, model=model)
            elapsed[model] += perf_counter()-start
            metrics[model].add(gold, predictions, learner.lexicon)
            for i, (expected, predicted) in enumerate(zip(gold.analyses, predictions)):
                if expected != predicted and len(errors[model]) < 30:
                    errors[model].append({'sentence_id': gold.example.id, 'token_index': i, 'form': gold.example.tokens[i], 'oov': gold.example.tokens[i] not in learner.lexicon, 'expected': expected.to_dict(), 'predicted': predicted.to_dict()})
    if not scored_count:
        raise ValueError('No evaluation sentences remain after removing training-source overlap')
    report = {'algorithm_id': ALGORITHM_ID, 'environment': {'python': sys.version.split()[0], 'platform': platform.platform()}, 'task': 'Supervised word lemmatization, POS and morphological feature prediction; not translation.',
              'protocol': 'Frozen model; evaluation receives tokens only; exact NFC token-sequence overlaps with training are excluded; supplied syntactic-word segmentation; punctuation included with nonpunctuation scores reported separately.',
              'split': split, 'training': file_info(train_path), 'evaluation': file_info(eval_path),
              'training_sentences': len(learner.records), 'training_tokens': learner.token_count,
              'training_labels': 'All available training annotations; no pretraining or external lexicon.',
              'evaluation_sentences_read': read_count, 'excluded_train_overlap_sentences': excluded,
              'limit_train': limit_train, 'limit_eval': limit_eval, 'training_seconds': train_seconds,
              'models': {model: {**metric.result(), 'prediction_seconds': elapsed[model], 'errors': errors[model]} for model, metric in metrics.items()}}
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    if model_path:
        learner.save(model_path)
    write_summary(report, destination.with_suffix('.md'))
    return report


def write_summary(report, path):
    def percent(value):
        return 'n/a' if value is None else f'{value:.1%}'
    lines = ['# Real-corpus analysis', '', report['task'], '',
             f"Split: {report['split']}. Training: {report['training_sentences']:,} sentences / {report['training_tokens']:,} annotated tokens. Excluded exact training-source overlaps: {report['excluded_train_overlap_sentences']}.", '',
             '| Model | Lemma | POS | Feature bundle | Joint token | OOV joint | Nonpunctuation joint | Sentence exact |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for model, metrics in report['models'].items():
        fields = ('lemma_accuracy', 'upos_accuracy', 'feats_accuracy', 'joint_accuracy', 'oov_joint_accuracy', 'nonpunct_joint_accuracy', 'sentence_exact_accuracy')
        lines.append('| ' + model + ' | ' + ' | '.join(percent(metrics[field]) for field in fields) + ' |')
    lines += ['', report['protocol'], '',
              'The lexicon baseline memorizes the most frequent analysis per form and falls back to an unchanged lemma plus the global majority POS/feature bundle for unknown forms. The affix learner uses learned suffix distributions, observable neighboring words, word shape, and reusable lemma edits. Neither model receives evaluation annotations or gold POS as an input.', '',
              'Corpus labels, lemmas and word segmentation are supplied supervision. These results measure morphological analysis, not discovery of arbitrary meanings or English translation. Large training corpora are not comparable to the small synthetic seed condition. Individual error samples, metric denominators, feature F1, file hashes, and timing diagnostics are in the companion JSON report.']
    Path(path).write_text('\n'.join(lines)+'\n')


def learning_curve(train_path, eval_path, output, budgets=(25, 100, 500, 1000), limit_eval=None):
    """Release training sentences in corpus order; never teach dev annotations."""
    training = list(read_corpus(train_path))
    if not training:
        raise ValueError('Empty training corpus')
    if any(budget < 1 for budget in budgets):
        raise ValueError('Learning budgets must be positive')
    checkpoints = sorted({0, len(training), *(b for b in budgets if b <= len(training))})
    training_sources = {g.example.tokens for g in training}
    evaluation = list(islice(read_corpus(eval_path), limit_eval))
    probes = [g for g in evaluation if g.example.tokens not in training_sources]
    if not probes:
        raise ValueError('No nonoverlapping development examples remain')
    learner = CorpusLearner()
    points = []
    position = 0
    for budget in checkpoints:
        while position < budget:
            gold = training[position]
            learner.correct(gold.example, gold.analyses)
            position += 1
        scores = {}
        for model in ('lexicon', 'affix'):
            metric = Metrics()
            for gold in probes:
                metric.add(gold, learner.predict(gold.example, model=model), learner.lexicon)
            retention = Metrics()
            for gold in training[:min(25, budget)]:
                retention.add(gold, learner.predict(gold.example, model=model), learner.lexicon)
            scores[model] = {'held_out': metric.result(), 'training_recall': retention.result()}
        points.append({'sentence_labels': budget, 'token_labels': learner.token_count, 'scores': scores})
    report = {'algorithm_id': ALGORITHM_ID, 'environment': {'python': sys.version.split()[0], 'platform': platform.platform()}, 'task': 'Development-only acquisition curve for supervised morphological analysis.',
              'protocol': 'Original training sentence order; complete sentence annotations released at each budget; all input words are observable, but no development annotations are taught; exact source overlaps with the complete training split excluded. Recall is scored separately on the first 25 released sentences.',
              'training': file_info(train_path), 'evaluation': file_info(eval_path),
              'evaluation_sentences': len(probes), 'excluded_train_overlap_sentences': len(evaluation)-len(probes),
              'limit_eval': limit_eval, 'points': points}
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Real-corpus acquisition curve', '', report['task'], '', report['protocol'], '',
             '| Sentence labels | Token labels | Lexicon joint | Affix joint | Affix OOV joint |',
             '|---:|---:|---:|---:|---:|']
    for point in points:
        def percent(value):
            return 'n/a' if value is None else f'{value:.1%}'
        scores = point['scores']
        lines.append(f"| {point['sentence_labels']} | {point['token_labels']} | {percent(scores['lexicon']['held_out']['joint_accuracy'])} | {percent(scores['affix']['held_out']['joint_accuracy'])} | {percent(scores['affix']['held_out']['oov_joint_accuracy'])} |")
    lines += ['', f"Evaluated {len(probes)} fixed development sentences. Evaluation limit: {limit_eval if limit_eval is not None else 'none'}. These are corpus-order prefix budgets, not randomized replicated learning curves. No claims about small-data translation follow from these scores."]
    destination.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    return report
