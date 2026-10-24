"""Read-only teaching review, source-conflict diagnostics and Unicode search."""
from collections import defaultdict

from .corpus import nfc
from .teaching import validate_predictions


def annotation_conflicts(project):
    groups = defaultdict(list)
    for example in project.examples():
        annotation = project.annotation(example.id)
        if annotation is not None:
            groups[example.tokens].append((example.id, annotation))
    conflicts = []
    for tokens, entries in groups.items():
        variants = {tuple(annotation['glosses']) for _, annotation in entries}
        if len(variants) > 1:
            conflicts.append({'tokens': list(tokens), 'annotations': [
                {'id': identifier, 'revision': annotation['revision'], 'glosses': annotation['glosses']}
                for identifier, annotation in entries]})
    return conflicts


def search(project, query, *, include_history=False):
    if not isinstance(query, str) or not query.strip():
        raise ValueError('Search query must be nonempty text')
    needle = nfc(query.strip()).casefold()
    results = []
    for example in project.examples():
        annotation = project.annotation(example.id)
        fields = {'id': example.id, 'source': ' '.join(example.tokens),
                  'annotation': ' '.join(annotation['glosses']) if annotation else ''}
        if include_history:
            fields['history'] = ' '.join(' '.join(row['glosses'])+' '+row['reason'] for row in project.history(example.id))
        matches = [name for name, value in fields.items() if needle in nfc(value).casefold()]
        if matches:
            results.append({'id': example.id, 'tokens': list(example.tokens), 'annotation': annotation,
                            'matched_fields': matches})
    return results


def relative_margin(word):
    candidates = word['candidates']
    if not candidates:
        return 0.0
    if len(candidates) == 1:
        return 1.0
    first, second = candidates[0]['score'], candidates[1]['score']
    total = abs(first)+abs(second)
    return max(0.0, min(1.0, (first-second)/total)) if total else 0.0


def review_queue(project, *, limit=10, include_reviewed=False, calibration=None):
    if type(limit) is not int or not 1 <= limit <= 1000 or type(include_reviewed) is not bool:
        raise ValueError('Review limit must be between 1 and 1000; include_reviewed must be boolean')
    identity = project.model_identity()
    conflicts = annotation_conflicts(project)
    conflicting_ids = {row['id'] for group in conflicts for row in group['annotations']}
    calibration_status = calibration.status(identity) if calibration is not None else 'unavailable'
    ranked = []
    for position, example in enumerate(project.examples()):
        annotation = project.annotation(example.id)
        conflict = example.id in conflicting_ids
        if annotation is not None and not include_reviewed and not conflict:
            continue
        predictions = validate_predictions(project.predict(example), example.tokens)
        unknown = sum(row['gloss'] is None for row in predictions)
        unseen = sum(not row['known_form'] for row in predictions)
        margins = [relative_margin(row) for row in predictions]
        estimates = [calibration.estimate(row, identity) if calibration is not None else None for row in predictions]
        error = 1-sum(item['estimated_accuracy'] for item in estimates)/len(estimates) if all(item is not None for item in estimates) else None
        reasons = []
        if conflict:
            reasons.append('same source has different verified annotations')
        if unknown:
            reasons.append('unsupported word glosses')
        if unseen:
            reasons.append('unseen source forms')
        if any(len(row['candidates']) > 1 for row in predictions):
            reasons.append('competing candidate glosses')
        row = {'id': example.id, 'tokens': list(example.tokens), 'annotation': annotation,
               'model_version': project.model_version, 'words': predictions,
               'unknown_words': unknown, 'unseen_forms': unseen, 'source_conflict': conflict,
               'review_reasons': reasons or ['not yet verified'], 'calibration_status': calibration_status,
               'word_accuracy_estimates': estimates, 'estimated_word_error_rate': error,
               'raw_margin_is_probability': False}
        # Unsupported items get attention before ranked estimates; a raw score is
        # never compared to a probability as though they shared the same units.
        key = (not conflict, -unknown/len(predictions), error is not None,
               -error if error is not None else -unseen/len(predictions), min(margins), position)
        ranked.append((key, row))
    if project.model_identity() != identity:
        raise ValueError('Model changed while ordering review items; reload and try again')
    ranked.sort(key=lambda item: item[0])
    return {'model_identity': identity, 'calibration_status': calibration_status,
            'ordering': 'source conflicts, unsupported gloss fraction, unavailable estimates, then estimated error or unseen forms and candidate ambiguity; stable insertion ties',
            'total_reviewable': len(ranked), 'source_conflicts': conflicts,
            'items': [row for _, row in ranked[:limit]]}
