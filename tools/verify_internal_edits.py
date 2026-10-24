"""Audit a completed internal-edit run from saved artifacts, without corpus input."""
from collections import Counter
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from decipher.corpus import TextExample
from decipher.gloss import GlossExample, lexical_key
from decipher.gloss_checkpoint import digest, encoded
from decipher.gloss_internal import InternalGlossOverlay
from tools.evaluate_internal_edits import score_pairs, source_fingerprint, write_json


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(directory):
    directory = Path(directory)
    def read(name):
        return json.loads((directory/name).read_text(encoding='utf-8'))
    def rows(name):
        return [json.loads(line) for line in (directory/name).read_text(encoding='utf-8').splitlines()]
    report = read('results.json')
    require(report['status'] == 'complete', 'Only complete runs can be audited')
    names = {'manifest.json', 'selected-rules.json', 'scoring-context.json', 'predictions.jsonl',
             'private-gold.jsonl', 'private-changes.jsonl', 'base-model.json.gz'}
    require(set(report['artifact_sha256']) == names, 'Missing or unexpected artifacts')
    for name in sorted(names):
        require(digest((directory/name).read_bytes()) == report['artifact_sha256'][name], f'Artifact checksum mismatch: {name}')
    require(source_fingerprint() == report['source']['implementation_sha256'], 'Use the recorded implementation to replay')
    manifest = read('manifest.json')
    require(digest(encoded(manifest)) == report['dataset']['manifest_sha256'], 'Membership manifest mismatch')
    predictions, answers = rows('predictions.jsonl'), rows('private-gold.jsonl')
    require(len(predictions) == len(answers) == report['dataset']['development_sentences'], 'Sentence count mismatch')
    require([row['id'] for row in predictions] == [row['id'] for row in answers], 'Private answers do not align')
    membership = [{'id': row['id'], 'source_sha256': digest(encoded(row['tokens']))} for row in predictions]
    require(membership == manifest['membership']['development'], 'Development membership/order changed')
    golds = [GlossExample(TextExample(row['id'], tuple(row['tokens'])), tuple(answer['glosses']))
             for row, answer in zip(predictions, answers)]
    baseline = [row['baseline'] for row in predictions]
    experimental = [row['experimental'] for row in predictions]
    context = read('scoring-context.json')['grounded_lexemes']
    scored, changed = score_pairs(golds, baseline, experimental, context)
    selected = {tuple(row['rule']) for row in read('selected-rules.json')}
    for row in changed:
        if row['baseline']['gloss'] == row['expected'] and row['experimental']['gloss'] != row['expected']:
            candidates = row['baseline']['candidates']
            row['baseline_winning_rule_displaced'] = bool(candidates and candidates[0].get('rule')
                                                         and tuple(candidates[0]['rule']) not in selected)
    for name, value in scored.items():
        require(value == report[name], f'Reconstructed scoring differs: {name}')
    require(changed == rows('private-changes.jsonl'), 'Changed-word records differ')
    require(sum(row.get('baseline_winning_rule_displaced', False) for row in changed)
            == report['regression_winning_rules_displaced'], 'Displaced-rule regression count differs')
    restored = InternalGlossOverlay.from_checkpoint(directory/'base-model.json.gz')
    rules = [{'rule': list(rule), 'support': len(restored._evidence[rule])} for rule in restored.selected_rules]
    require(rules == read('selected-rules.json'), 'Reconstructed rules differ')
    require([list(key) for key in sorted(restored.base.paradigms)] == context, 'Grounded scoring context differs')
    require([{'id': row.example.id, 'source_sha256': digest(encoded(row.example.tokens))}
             for row in restored.base.records.values()] == manifest['membership']['training'], 'Training membership/order changed')
    recovery = Counter()
    for gold, left, right in zip(golds, baseline, experimental):
        require(restored.base.predict(gold.example) == left, f'Base candidate replay differs: {gold.example.id}')
        require(restored.predict(gold.example) == right, f'Overlay candidate replay differs: {gold.example.id}')
        for word, target, prediction in zip(gold.example.tokens, gold.glosses, right):
            key = lexical_key(target)
            if word in restored.base.lexicon or not key or key not in restored.base.paradigms or prediction['gloss'] == target:
                continue
            recovered = any(lexical_key(gloss) == key for row in restored.recoveries(word) if row['rule'][0] == 'internal'
                            for anchor in row['anchors'] for gloss in restored.base.lexicon[anchor])
            recovery['internal_anchor_for_gold_lexeme' if recovered else 'no_selected_internal_anchor_for_gold_lexeme'] += 1
    require(dict(recovery) == report['grounded_error_recovery'], 'Grounded recovery diagnostics differ')
    return {'schema_version': 1, 'language': report['language'], 'verified': True,
            'sentences': len(golds), 'words': report['baseline']['counts']['words'], 'changed_words': len(changed),
            'checks': ['artifact_checksums', 'frozen_implementation', 'training_and_development_membership',
                       'all_scores_and_samples', 'all_changed_word_records', 'grounded_failure_categories_and_recovery',
                       'checkpoint_selected_rules', 'all_base_and_overlay_full_candidates'],
            'results_sha256': digest((directory/'results.json').read_bytes()),
            'verifier_sha256': digest(Path(__file__).read_text(encoding='utf-8').encode('utf-8')),
            'scope': 'Independent saved-artifact replay; no corpus files, new labels or model corrections'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        require(not args.output.exists(), 'Choose a fresh audit report path')
        result = verify(args.run_dir)
        write_json(args.output, result)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f'Artifact audit failed: {exc}\n')


if __name__ == '__main__':
    main()
