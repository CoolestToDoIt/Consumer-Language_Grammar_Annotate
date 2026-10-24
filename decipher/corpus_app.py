"""Corpus training, evaluation, prediction and correction commands."""
import argparse
import json
from pathlib import Path
import sys
from .corpus import TextExample, nfc, read_corpus
from .corpus_learner import CorpusLearner, ALGORITHM_ID
from .corpus_evaluate import evaluate_corpus, learning_curve, train


def public_inputs(path):
    path = Path(path)
    if path.suffix == '.conllu':
        for gold in read_corpus(path):
            yield gold.example
    else:
        with path.open(encoding='utf-8-sig') as handle:
            for i, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                if path.suffix == '.jsonl':
                    row = json.loads(line)
                    tokens, identifier = row['tokens'], row['id']
                    if not isinstance(tokens, list) or any(not isinstance(t, str) or not t.strip() or any(c in t for c in '\r\n\t') for t in tokens):
                        raise ValueError(f'{path}:{i}: expected nonempty word tokens')
                else:
                    tokens, identifier = line.split(), f'{path.name}:{i}'
                if not isinstance(identifier, str) or not identifier or not tokens:
                    raise ValueError('Input needs a nonempty id and tokens')
                yield TextExample(identifier, tuple(nfc(t) for t in tokens))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Learn lemma/POS/morphology from real annotated corpora')
    commands = parser.add_subparsers(dest='command', required=True)
    fit = commands.add_parser('train')
    fit.add_argument('--train', required=True)
    fit.add_argument('--model', required=True)
    fit.add_argument('--baseline', choices=('memory', 'lexicon', 'affix'), default='affix')
    fit.add_argument('--limit', type=int)
    evaluate = commands.add_parser('evaluate')
    evaluate.add_argument('--train', required=True)
    evaluate.add_argument('--eval', required=True)
    evaluate.add_argument('--split', choices=('dev', 'test'), default='dev')
    evaluate.add_argument('--output', required=True)
    evaluate.add_argument('--save-model')
    evaluate.add_argument('--limit-train', type=int)
    evaluate.add_argument('--limit-eval', type=int)
    evaluate.add_argument('--models', nargs='+', choices=('memory', 'lexicon', 'affix'), default=('lexicon', 'affix'))
    curve = commands.add_parser('curve')
    curve.add_argument('--train', required=True)
    curve.add_argument('--eval', required=True, help='Development corpus; keep final test data separate')
    curve.add_argument('--output', required=True)
    curve.add_argument('--budgets', nargs='+', type=int, default=(25, 100, 500, 1000))
    curve.add_argument('--limit-eval', type=int)
    analyze = commands.add_parser('analyze')
    analyze.add_argument('--model', required=True)
    source = analyze.add_mutually_exclusive_group(required=True)
    source.add_argument('--input')
    source.add_argument('--text', help='Whitespace-segmented words; prefer JSONL/CoNLL-U for corpus tokenization')
    analyze.add_argument('--output')
    correct = commands.add_parser('correct')
    correct.add_argument('--model', required=True)
    correct.add_argument('--annotations', required=True)
    args = parser.parse_args(argv)
    for name in ('limit', 'limit_train', 'limit_eval'):
        value = getattr(args, name, None)
        if value is not None and value < 1:
            parser.error(f'--{name.replace("_", "-")} must be positive')
    try:
        if args.command == 'train':
            learner, seconds = train(args.train, args.baseline, args.limit)
            learner.save(args.model)
            print(f'Saved {len(learner.records):,} sentences / {learner.token_count:,} labeled tokens in {seconds:.2f}s to {args.model}')
        elif args.command == 'evaluate':
            report = evaluate_corpus(args.train, args.eval, args.output, args.split, args.save_model, args.limit_train, args.limit_eval, tuple(args.models))
            for model, metrics in report['models'].items():
                def percentage(value):
                    return 'n/a' if value is None else f'{value:.1%}'
                print(f"{model}: lemma {percentage(metrics['lemma_accuracy'])}; POS {percentage(metrics['upos_accuracy'])}; joint {percentage(metrics['joint_accuracy'])}; OOV joint {percentage(metrics['oov_joint_accuracy'])}")
            print(f"Excluded {report['excluded_train_overlap_sentences']} training-source overlaps; saved {args.output}")
        elif args.command == 'curve':
            report = learning_curve(args.train, args.eval, args.output, tuple(args.budgets), args.limit_eval)
            for point in report['points']:
                score = point['scores']['affix']['held_out']['joint_accuracy']
                print(f"{point['sentence_labels']:,} sentences / {point['token_labels']:,} token labels: {score:.1%} joint")
        elif args.command == 'analyze':
            learner = CorpusLearner.load(args.model)
            if args.text is not None:
                tokens = tuple(nfc(t) for t in args.text.split())
                if not tokens:
                    raise ValueError('Text cannot be empty')
                examples = [TextExample('input', tokens)]
            else:
                examples = public_inputs(args.input)
            handle = Path(args.output).open('w', encoding='utf-8') if args.output else sys.stdout
            try:
                for example in examples:
                    prediction = learner.predict(example)
                    row = {'id': example.id, 'tokens': list(example.tokens), 'analyses': [a.to_dict() for a in prediction], 'model_version': learner.version, 'algorithm_id': ALGORITHM_ID, 'verified_recall': example.tokens in learner.sentence_memory}
                    print(json.dumps(row, ensure_ascii=False), file=handle)
            finally:
                if args.output:
                    handle.close()
        else:
            learner = CorpusLearner.load(args.model)
            # Parse and validate the entire update before changing the checkpoint.
            updates = list(read_corpus(args.annotations))
            for update in updates:
                previous = learner.records.get(update.example.id)
                if previous is not None and previous.example != update.example:
                    raise ValueError('A correction ID cannot refer to different source tokens')
            changes = sum(learner.correct(g.example, g.analyses) for g in updates)
            learner.save(args.model)
            print(f'Applied {changes} new/revised sentences; version {learner.version}')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f'Corpus error: {exc}\n')

if __name__ == '__main__':
    main()
