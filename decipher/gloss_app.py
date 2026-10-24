"""Source-only interlinear glossing commands."""
import argparse
import json
from .corpus import TextExample
from .gloss import GlossLearner, load_gloss
from .gloss_evaluate import evaluate_gloss, online_gloss


def main(argv=None):
    parser=argparse.ArgumentParser(description='Learn word glosses from source-only annotated examples')
    commands=parser.add_subparsers(dest='command',required=True)
    evaluate=commands.add_parser('evaluate')
    evaluate.add_argument('--train',required=True)
    evaluate.add_argument('--eval',required=True)
    evaluate.add_argument('--output',required=True)
    evaluate.add_argument('--split',choices=('dev','test'),default='dev')
    fit=commands.add_parser('train')
    fit.add_argument('--train',required=True)
    fit.add_argument('--model',required=True)
    fit.add_argument('--mode',choices=('memory','analogy','rules'),default='rules')
    predict=commands.add_parser('predict')
    predict.add_argument('--model',required=True)
    predict.add_argument('--text',required=True)
    stream=commands.add_parser('stream')
    stream.add_argument('--train',required=True)
    stream.add_argument('--dev',required=True)
    stream.add_argument('--run-dir',required=True)
    stream.add_argument('--support',type=int,default=10)
    stream.add_argument('--stream',type=int,default=100)
    stream.add_argument('--delays',nargs='+',type=int,default=(0,5,20))
    stream.add_argument('--policies',nargs='+',choices=('all','corrections'),default=('all',))
    stream.add_argument('--probe-every',type=int,default=25)
    args=parser.parse_args(argv)
    try:
        if args.command=='evaluate':
            evaluate_gloss(args.train,args.eval,args.output,args.split)
        elif args.command=='stream':
            online_gloss(args.train,args.dev,args.run_dir,args.support,args.stream,tuple(args.delays),tuple(args.policies),args.probe_every)
        elif args.command=='train':
            records,stats=load_gloss(args.train,skip_misaligned=True)
            if not records:
                raise ValueError('No aligned training sentences')
            model=GlossLearner(args.mode)
            for record in records:
                model.correct(record.example,record.glosses)
            model.save(args.model)
            print(f'Saved {len(records)} aligned sentences; reader diagnostics: {stats}')
        else:
            tokens=tuple(args.text.split())
            if not tokens:
                raise ValueError('Text cannot be empty')
            model=GlossLearner.load(args.model)
            print(json.dumps(model.predict(TextExample('input',tokens)),ensure_ascii=False,indent=2))
    except (OSError,ValueError,KeyError,TypeError) as exc:
        parser.exit(2,f'Glossing error: {exc}\n')

if __name__=='__main__':
    main()
