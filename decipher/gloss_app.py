"""Source-only interlinear glossing commands."""
import argparse
import json
import sys
from .corpus import TextExample
from .gloss import GlossLearner, load_gloss
from .gloss_evaluate import evaluate_gloss, online_gloss, report_gloss, resume_gloss


def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if argv[:1]==['teach']:
        from .teaching_app import main as teaching_main
        return teaching_main(argv[1:])
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
    stream.add_argument('--modes',nargs='+',choices=('memory','analogy','rules'),default=('memory','analogy','rules'))
    stream.add_argument('--max-rules',type=int,default=512)
    stream.add_argument('--paradigm-window',type=int,default=32)
    stream.add_argument('--max-inputs',type=int,help='Stop after this many stream inputs per run; keep pending labels queued')
    stream.add_argument('--checkpoint-every',type=int,default=25)
    stream.add_argument('--report-dir',help='Fresh directory for compact JSON and Markdown matrix summaries')
    resume=commands.add_parser('resume',help='Continue one gloss run from its atomic checkpoint')
    resume.add_argument('--checkpoint',required=True)
    resume.add_argument('--run-dir',help='Original run directory (default) or an empty new directory')
    resume.add_argument('--max-inputs',type=int,help='Maximum additional stream inputs to process')
    resume.add_argument('--checkpoint-every',type=int,default=25)
    report=commands.add_parser('report',help='Reconstruct a run report from saved predictions, feedback and private scoring data')
    report.add_argument('--checkpoint',required=True)
    report.add_argument('--output',required=True)
    teach=commands.add_parser('teach',help='Teach/review a language project through its workspace adapter')
    teach.add_argument('teaching_args',nargs=argparse.REMAINDER)
    args=parser.parse_args(argv)
    try:
        if args.command=='teach':
            from .teaching_app import main as teaching_main
            teaching_main(args.teaching_args)
        elif args.command=='evaluate':
            evaluate_gloss(args.train,args.eval,args.output,args.split)
        elif args.command=='stream':
            online_gloss(args.train,args.dev,args.run_dir,args.support,args.stream,tuple(args.delays),tuple(args.policies),args.probe_every,
                         modes=tuple(args.modes),max_rules=args.max_rules,paradigm_window=args.paradigm_window,
                         max_inputs=args.max_inputs,checkpoint_every=args.checkpoint_every,report_dir=args.report_dir)
        elif args.command=='resume':
            result=resume_gloss(args.checkpoint,args.run_dir,args.max_inputs,args.checkpoint_every)
            print(f"Processed {result['processed_stream_inputs']} stream inputs; pending answers: {result['pending']}; complete: {result['complete']}")
        elif args.command=='report':
            report_gloss(args.checkpoint,args.output)
            print(f'Reconstructed metrics: {args.output}')
        elif args.command=='train':
            records,stats=load_gloss(args.train,skip_misaligned=True)
            if not records:
                raise ValueError('No aligned training sentences')
            model=GlossLearner(args.mode).fit(records)
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
