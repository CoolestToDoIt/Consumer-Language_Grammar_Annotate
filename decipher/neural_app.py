"""Optional neural training and development benchmark CLI."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
from .neural import MODES, NeuralConfig, NeuralLearner
from .neural_experiment import synthetic_task, corpus_task, run, write_experiment_report
from .online import OnlineSession


def main(argv=None):
    parser=argparse.ArgumentParser(description='Byte-level neural adaptation and replay experiments')
    commands=parser.add_subparsers(dest='command',required=True)
    benchmark=commands.add_parser('benchmark')
    benchmark.add_argument('--presets',nargs='+',choices=('A','B','C'),default=('A','B','C'))
    benchmark.add_argument('--language-seeds',nargs='+',type=int,default=(7,))
    corpus=commands.add_parser('corpus-benchmark')
    corpus.add_argument('--train',required=True)
    corpus.add_argument('--dev',required=True)
    corpus.add_argument('--support',type=int,default=25)
    fit=commands.add_parser('fit')
    fit.add_argument('--pairs',required=True,help='JSONL objects with id, source, target')
    fit.add_argument('--run-dir',required=True)
    fit.add_argument('--resume')
    predict=commands.add_parser('predict')
    predict.add_argument('--session',required=True)
    predict.add_argument('--source',required=True)
    predict.add_argument('--beam-size',type=int,default=3)
    predict.add_argument('--device',default='cpu',choices=('cpu','auto','mps','cuda'))
    for command in (benchmark,corpus):
        command.add_argument('--run-dir',required=True)
        command.add_argument('--report-dir',required=True)
        command.add_argument('--model-seeds',nargs='+',type=int,default=(7,))
        command.add_argument('--modes',nargs='+',choices=MODES,default=MODES)
        command.add_argument('--delays',nargs='+',type=int,default=(0,))
        command.add_argument('--policies',nargs='+',choices=('all','corrections'),default=('all',))
        command.add_argument('--stream',type=int,default=60)
        command.add_argument('--probes',type=int,default=30)
        command.add_argument('--probe-every',type=int,default=10)
    for command in (benchmark,corpus,fit):
        command.add_argument('--embedding',type=int,default=64)
        command.add_argument('--hidden',type=int,default=128)
        command.add_argument('--learning-rate',type=float,default=.0003)
        command.add_argument('--update-steps',type=int,default=2)
        command.add_argument('--replay-batch',type=int,default=15)
        command.add_argument('--reservoir-size',type=int,default=2000)
        command.add_argument('--max-source-bytes',type=int,default=512)
        command.add_argument('--max-target-bytes',type=int,default=96)
        command.add_argument('--device',choices=('cpu','auto','mps','cuda'),default='cpu')
        command.add_argument('--threads',type=int,default=1)
    fit.add_argument('--mode',choices=MODES,default='hybrid')
    fit.add_argument('--delay',type=int,default=0)
    args=parser.parse_args(argv)
    try:
        import torch
        if args.command == 'predict':
            session=OnlineSession.load(args.session,device=args.device)
            print(json.dumps(session.learner.predict(args.source,beam_size=args.beam_size),ensure_ascii=False,indent=2))
            return
        if args.threads<1:
            raise ValueError('threads must be positive')
        torch.set_num_threads(args.threads)
        config=NeuralConfig(embedding=args.embedding,hidden=args.hidden,learning_rate=args.learning_rate,update_steps=args.update_steps,
                            replay_batch=args.replay_batch,reservoir_size=args.reservoir_size,max_source_bytes=args.max_source_bytes,
                            max_target_bytes=args.max_target_bytes,device=args.device)
        if args.command == 'fit':
            if args.delay<0:
                raise ValueError('delay must be nonnegative')
            directory=Path(args.run_dir)
            if directory.exists() and any(directory.iterdir()) and not args.resume:
                raise ValueError('Run directory is not empty; choose a new directory or explicitly resume')
            session=OnlineSession.load(args.resume,device=args.device) if args.resume else OnlineSession(NeuralLearner(config,args.mode),'paired-text')
            if args.resume and session.learner.mode!=args.mode:
                raise ValueError('Resume mode must match the checkpoint')
            with Path(args.pairs).open() as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    row=json.loads(line)
                    if row['id'] in session.sources:
                        if session.sources[row['id']]!=row['source']:
                            raise ValueError('Previously predicted ID has different source text')
                    else:
                        session.predict(row['id'],row['source'],beam_size=1)
                    session.feedback(row['id'],row['target'],delay=args.delay,revision=row.get('revision',0))
            session.save(directory/'session.pt')
            session.export(directory)
            print(f'Arrived answers: {len(session.processed)}; pending: {len(session.pending)}; optimizer steps: {session.learner.optimizer_steps}')
            return
        if min(args.stream,args.probes,args.probe_every)<1 or any(delay<0 for delay in args.delays):
            raise ValueError('Stream/probe sizes must be positive and delays nonnegative')
        if args.command=='benchmark':
            if args.stream>60 or args.probes>30:
                raise ValueError('Synthetic dataset has at most 60 stream examples and 30 probes')
            tasks=[synthetic_task(preset,seed,args.stream,args.probes) for preset in args.presets for seed in args.language_seeds]
            baseline='rules'
        else:
            if args.support<0:
                raise ValueError('Support size must be nonnegative')
            tasks=[corpus_task(args.train,args.dev,args.support,args.stream,args.probes,config)]
            baseline='affix'
        rows=[]
        # Run each condition sequentially; default CPU memory is bounded.
        for task in tasks:
            for seed in args.model_seeds:
                for delay in args.delays:
                    for policy in args.policies:
                        for mode in (baseline,*args.modes):
                            directory=Path(args.run_dir)/task['name']/f'seed-{seed}'/f'{mode}-delay-{delay}-{policy}'
                            if directory.exists() and any(directory.iterdir()):
                                raise ValueError(f'Refusing to overwrite existing run: {directory}')
                            metrics=run(task,mode,replace(config,seed=seed),directory,delay,policy,args.probe_every)
                            rows.append({'task':task['name'],'kind':task['kind'],'metrics':metrics,'run_directory':str(directory)})
                            write_experiment_report(rows,args.report_dir,'Development-only online comparisons. Shared source examples, seed labels, stream order, probe set and answer-delay schedule. All-label feedback is the main matched-supervision condition; corrections-only feedback may produce different label exposure and is reported separately. Pending labels are not drained.')
    except (OSError,ValueError,KeyError,TypeError) as exc:
        parser.exit(2,f'Neural experiment error: {exc}\n')

if __name__=='__main__':
    main()
