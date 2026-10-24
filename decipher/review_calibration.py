"""Held-out correctness calibration for frozen word-gloss predictions.

Empirical strata use candidate kind, known-form status and relative score margin.
Raw rule scores are features, never probabilities. Validation is descriptive for
the supplied development population, not a language-level statistical guarantee.
"""
from collections import defaultdict
import json
import math
from pathlib import Path

from .corpus import TextExample
from .corpus_evaluate import file_info
from .gloss import GlossExample, load_gloss
from .gloss_checkpoint import digest, encoded
from .review import relative_margin
from .teaching import aligned_glosses, public_example, validate_predictions

METHOD = 'empirical-gloss-correctness-strata-v1'
DEFAULTS = {'min_group': 20, 'min_samples': 100, 'max_ece': .10, 'max_brier_regression': .005,
            'min_validation_coverage': .90, 'prior_weight': 2.0}


def _key(word, fine=True):
    kind = word['candidates'][0]['kind'] if word['candidates'] else 'unknown'
    values = [kind, word['known_form']]
    if fine:
        values.append(min(3, int(relative_margin(word)*4)))
    return json.dumps(values, separators=(',', ':'))


def probability_metrics(probabilities, answers):
    if len(probabilities) != len(answers):
        raise ValueError('Probability/answer counts must align')
    bins = [[] for _ in range(10)]
    for probability, answer in zip(probabilities, answers):
        if (type(probability) not in (int, float) or not math.isfinite(probability)
                or not 0 <= probability <= 1 or type(answer) not in (int, bool) or answer not in (0, 1)):
            raise ValueError('Expected finite probabilities in [0,1] and binary correctness labels')
        bins[min(9, int(probability*10))].append((probability, answer))
    reliability = []
    for index, values in enumerate(bins):
        reliability.append({'lower': index/10, 'upper': (index+1)/10, 'count': len(values),
                            'mean_estimate': sum(p for p, _ in values)/len(values) if values else None,
                            'observed_accuracy': sum(y for _, y in values)/len(values) if values else None})
    total = len(answers)
    return {'words': total, 'brier': sum((p-y)**2 for p, y in zip(probabilities, answers))/total if total else None,
            'ece': sum(row['count']*abs(row['mean_estimate']-row['observed_accuracy'])
                       for row in reliability if row['count'])/total if total else None,
            'reliability_bins': reliability}


def _configuration(config):
    if set(config) != set(DEFAULTS):
        raise ValueError('Unsupported calibration configuration fields')
    if any(type(config[key]) is not int or config[key] < 1 for key in ('min_group', 'min_samples')):
        raise ValueError('Calibration group/sample minima must be positive integers')
    if any(type(config[key]) not in (float, int) or not math.isfinite(config[key]) or not 0 <= config[key] <= 1
           for key in ('max_ece', 'max_brier_regression', 'min_validation_coverage')):
        raise ValueError('Calibration validation thresholds must lie in [0,1]')
    if type(config['prior_weight']) not in (float, int) or not math.isfinite(config['prior_weight']) or config['prior_weight'] < 0:
        raise ValueError('Calibration prior weight must be finite and nonnegative')


class Calibration:
    def __init__(self, model_identity, *, config=None):
        self.model_identity = model_identity
        self.config = dict(DEFAULTS if config is None else config)
        _configuration(self.config)
        self.groups, self.coarse = {}, {}
        self.fit_words, self.fit_correct = 0, 0
        self.validation = {}
        self.manifest = {}

    @property
    def prior(self):
        return self.fit_correct/self.fit_words if self.fit_words else 0.0

    def _estimate(self, word):
        if word['gloss'] is None:
            return {'estimated_accuracy': 0.0, 'calibration_examples': self.fit_words,
                    'basis': 'Abstention cannot exactly match a nonempty gold gloss'}
        for groups, key, basis in ((self.groups, _key(word), 'candidate-kind/known-form/margin stratum'),
                                   (self.coarse, _key(word, False), 'candidate-kind/known-form backoff')):
            group = groups.get(key)
            if group is not None and group['words'] >= self.config['min_group']:
                weight = self.config['prior_weight']
                return {'estimated_accuracy': (group['correct']+weight*self.prior)/(group['words']+weight),
                        'calibration_examples': group['words'], 'basis': basis}
        return None

    def status(self, model_identity):
        if model_identity != self.model_identity:
            return 'stale'
        if self.fit_words < self.config['min_samples'] or self.validation.get('scored_words', 0) < self.config['min_samples']:
            return 'insufficient_data'
        if self.validation['coverage'] < self.config['min_validation_coverage']:
            return 'insufficient_coverage'
        measured, baseline = self.validation['estimated'], self.validation['constant_fit_prior']
        if measured['ece'] > self.config['max_ece'] or measured['brier'] > baseline['brier']+self.config['max_brier_regression']:
            return 'validation_failed'
        return 'validated'

    def estimate(self, word, model_identity):
        if self.status(model_identity) != 'validated':
            return None
        estimate = self._estimate(word)
        if estimate is not None:
            estimate = {**estimate, 'validation_ece': self.validation['estimated']['ece'],
                        'validation_words': self.validation['scored_words'],
                        'scope': 'Supplied held-out development population at this exact model identity'}
        return estimate

    def state(self):
        return {'schema_version': 1, 'method': METHOD, 'model_identity': self.model_identity,
                'config': self.config, 'fit_words': self.fit_words, 'fit_correct': self.fit_correct,
                'groups': self.groups, 'coarse': self.coarse, 'validation': self.validation,
                'manifest': self.manifest, 'status': self.status(self.model_identity)}

    def save(self, path):
        destination = Path(path)
        if destination.exists():
            raise ValueError('Calibration destination already exists; choose a fresh artifact path')
        destination.parent.mkdir(parents=True, exist_ok=True)
        from .teaching_fixture import _atomic_json
        state = self.state()
        _atomic_json(destination, {'schema_version': 1, 'sha256': digest(encoded(state)), 'calibration': state})

    @classmethod
    def load(cls, path):
        try:
            envelope = json.loads(Path(path).read_text(encoding='utf-8'))
            state = envelope['calibration']
            if (type(envelope.get('schema_version')) is not int or envelope['schema_version'] != 1
                    or state.get('schema_version') != 1 or state.get('method') != METHOD
                    or digest(encoded(state)) != envelope['sha256']):
                raise ValueError('Unsupported or corrupted calibration artifact')
            if not isinstance(state['model_identity'], str) or not state['model_identity']:
                raise ValueError('Invalid calibrated-model identity')
            model = cls(state['model_identity'], config=state['config'])
            for key in ('fit_words', 'fit_correct'):
                if type(state[key]) is not int or state[key] < 0:
                    raise ValueError('Invalid calibration annotation counts')
                setattr(model, key, state[key])
            if model.fit_correct > model.fit_words:
                raise ValueError('Correct count exceeds calibration word count')
            for name, length in (('groups', 3), ('coarse', 2)):
                groups = state[name]
                if not isinstance(groups, dict):
                    raise ValueError('Calibration strata must be objects')
                for key, group in groups.items():
                    features = json.loads(key)
                    if (not isinstance(features, list) or len(features) != length or not isinstance(features[0], str)
                            or type(features[1]) is not bool or (length == 3 and (type(features[2]) is not int or not 0 <= features[2] <= 3))
                            or set(group) != {'words', 'correct'}
                            or type(group['words']) is not int or type(group['correct']) is not int
                            or not 0 <= group['correct'] <= group['words']):
                        raise ValueError('Invalid calibration stratum')
                if sum(group['words'] for group in groups.values()) != model.fit_words or sum(group['correct'] for group in groups.values()) != model.fit_correct:
                    raise ValueError('Calibration strata disagree with annotation counts')
                setattr(model, name, groups)
            model.validation, model.manifest = state['validation'], state['manifest']
            for key in ('words', 'scored_words', 'unsupported_words'):
                if type(model.validation[key]) is not int or model.validation[key] < 0:
                    raise ValueError('Invalid saved calibration validation counts')
            total = model.validation['words']
            scored = model.validation['scored_words']
            coverage = model.validation['coverage']
            if (total < 1 or scored+model.validation['unsupported_words'] != total
                    or type(coverage) not in (int, float) or not math.isfinite(coverage)
                    or coverage != scored/total):
                raise ValueError('Calibration validation coverage disagrees with its counts')
            for measured in ('estimated', 'constant_fit_prior'):
                metrics = model.validation[measured]
                if type(metrics['words']) is not int or metrics['words'] != scored:
                    raise ValueError('Calibration metric denominator differs from validation count')
                for key in ('ece', 'brier'):
                    if ((metrics[key] is None) != (scored == 0)
                            or (metrics[key] is not None and (type(metrics[key]) not in (int, float)
                                or not math.isfinite(metrics[key]) or not 0 <= metrics[key] <= 1))):
                        raise ValueError('Invalid saved calibration validation metric')
            if model.status(model.model_identity) != state['status']:
                raise ValueError('Saved calibration status disagrees with its validation gate')
            return model
        except (KeyError, TypeError, AttributeError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f'Invalid calibration artifact: {exc}') from exc


def _validated_records(records):
    result = []
    for record in records:
        if not isinstance(record, GlossExample):
            raise ValueError('Calibration requires complete source/gloss records')
        example = public_example(record.example.id, record.example.tokens)
        result.append(GlossExample(example, aligned_glosses(record.glosses, example.tokens)))
    return result


def _observations(project, records):
    result = []
    for record in records:
        predictions = validate_predictions(project.predict(record.example), record.example.tokens)
        result.extend((word, word['gloss'] == gold) for word, gold in zip(predictions, record.glosses))
    return result


def build_calibration(project, fit, validation, *, config=None, label_policy='all'):
    if label_policy != 'all':
        raise ValueError('Calibration needs complete all-label evaluation, not correction-only review logs')
    fit, validation = _validated_records(fit), _validated_records(validation)
    if not fit or not validation:
        raise ValueError('Need nonempty disjoint calibration and validation sets')
    training = {public_example('training', words).tokens for words in project.training_sources()}
    sources = [record.example.tokens for record in fit+validation]
    identifiers = [record.example.id for record in fit+validation]
    if len(sources) != len(set(sources)) or len(identifiers) != len(set(identifiers)) or training.intersection(sources):
        raise ValueError('Calibration, validation and learner training must have disjoint whole sources and unique evaluation IDs')
    identity = project.model_identity()
    model = Calibration(identity, config=config)
    fitted = _observations(project, fit)
    groups, coarse = defaultdict(lambda: {'words': 0, 'correct': 0}), defaultdict(lambda: {'words': 0, 'correct': 0})
    for word, correct in fitted:
        for collection, key in ((groups, _key(word)), (coarse, _key(word, False))):
            collection[key]['words'] += 1
            collection[key]['correct'] += correct
    model.groups, model.coarse = dict(groups), dict(coarse)
    model.fit_words, model.fit_correct = len(fitted), sum(correct for _, correct in fitted)
    held_out = _observations(project, validation)
    estimates, answers = [], []
    for word, correct in held_out:
        estimate = model._estimate(word)
        if estimate is not None:
            estimates.append(estimate['estimated_accuracy'])
            answers.append(correct)
    model.validation = {'words': len(held_out), 'scored_words': len(answers),
                        'unsupported_words': len(held_out)-len(answers),
                        'coverage': len(answers)/len(held_out),
                        'estimated': probability_metrics(estimates, answers),
                        'constant_fit_prior': probability_metrics([model.prior]*len(answers), answers)}
    def selection(records):
        return {'sentences': len(records), 'word_labels': sum(len(row.glosses) for row in records),
                'records': [{'id': row.example.id, 'source_sha256': digest(encoded(row.example.tokens))} for row in records]}
    model.manifest = {'fit': selection(fit), 'validation': selection(validation), 'label_policy': label_policy,
                      'task': 'Probability the original top word gloss exactly matches a supplied nonempty gold gloss',
                      'model_frozen': True, 'learner_training_labels_added': 0,
                      'validation_scope': 'Descriptive held-out development sample; word observations are not independent languages',
                      'method_reference': 'https://proceedings.mlr.press/v70/guo17a.html (reliability/ECE background; this is empirical stratification, not temperature scaling)'}
    if project.model_identity() != identity:
        raise ValueError('Learner changed during calibration; discard this run and retry with a frozen model')
    return model


def prepare_calibration(project, fit_records, validation_records):
    """Explicit exclusions for file-based evaluation; build_calibration is strict."""
    occupied = set(project.training_sources())
    filters = {}
    selected = []
    for role, records in (('fit', fit_records), ('validation', validation_records)):
        unique, seen = [], {}
        counts = {'training_or_earlier_split_overlap': 0, 'duplicate_sources': 0, 'conflicting_duplicates': 0,
                  'excluded_ids': []}
        for record in _validated_records(records):
            source = record.example.tokens
            if source in occupied:
                counts['training_or_earlier_split_overlap'] += 1
                counts['excluded_ids'].append(record.example.id)
            elif source in seen:
                counts['duplicate_sources'] += 1
                counts['conflicting_duplicates'] += record.glosses != seen[source].glosses
                counts['excluded_ids'].append(record.example.id)
            else:
                seen[source] = record
                unique.append(record)
        occupied.update(seen)
        selected.append(unique)
        filters[role] = counts
    return *selected, filters


def calibrate_files(project, fit_path, validation_path, output):
    fit, fit_reader = load_gloss(fit_path, skip_misaligned=True)
    validation, validation_reader = load_gloss(validation_path, skip_misaligned=True)
    fit, validation, filters = prepare_calibration(project, fit, validation)
    calibration = build_calibration(project, fit, validation)
    calibration.manifest.update({'fit_file': file_info(fit_path), 'validation_file': file_info(validation_path),
                                 'readers': {'fit': fit_reader, 'validation': validation_reader}, 'filters': filters})
    calibration.save(output)
    return {'artifact': str(output), 'status': calibration.status(project.model_identity()),
            'fit_word_labels': calibration.fit_words, 'validation': calibration.validation,
            'note': 'Estimates are disabled unless held-out validation passes; teaching changes invalidate this artifact.'}
