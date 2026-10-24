"""Versioned episode identity and explicit public/private dataset exports."""
import hashlib
import json
from pathlib import Path
from .generator import episode

DATASET_VERSION = 2


def manifest(preset, seed):
    _, roots, support, stream, probes = episode(preset, seed)
    splits = {'support': support, 'stream': stream, 'probes': probes}
    all_examples = support + stream + probes
    sources = [g.example.source for g in all_examples]
    ids = [g.example.id for g in all_examples]
    meanings = [json.dumps(g.meaning, sort_keys=True) for g in all_examples]
    if len(set(sources)) != len(sources) or len(set(ids)) != len(ids) or len(set(meanings)) != len(meanings):
        raise ValueError('Dataset splits overlap or contain duplicate forms/meanings/IDs')
    grounded = set(roots.values())
    if any(g.meaning[slot] not in grounded for g in all_examples for slot in ('agent', 'patient', 'predicate')):
        raise ValueError('Dataset contains ungrounded primitives')
    public = {'roots': roots, 'splits': {name: [{'id': g.example.id, 'source': g.example.source} for g in group] for name, group in splits.items()}}
    digest = hashlib.sha256(json.dumps(public, sort_keys=True).encode()).hexdigest()
    return {'dataset_version': DATASET_VERSION, 'preset': preset, 'seed': seed, 'fingerprint': digest,
            'root_anchors': len(roots), 'split_ids': {name: [g.example.id for g in group] for name, group in splits.items()}}


def identity(preset, seed):
    metadata = manifest(preset, seed)
    return {key: metadata[key] for key in ('dataset_version', 'preset', 'seed', 'fingerprint')}


def export_dataset(directory, preset='A', seed=7):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    metadata = manifest(preset, seed)
    _, roots, support, stream, probes = episode(preset, seed)
    (directory/'manifest.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (directory/'roots.json').write_text(json.dumps(roots, indent=2) + '\n')
    for name, group in (('support', support), ('stream', stream), ('probes', probes)):
        (directory/f'{name}.jsonl').write_text(''.join(json.dumps({'id': g.example.id, 'source': g.example.source}) + '\n' for g in group))
    (directory/'teacher-only.jsonl').write_text(''.join(json.dumps({'id': g.example.id, 'meaning': g.meaning}) + '\n' for g in support + stream + probes))
    return metadata
