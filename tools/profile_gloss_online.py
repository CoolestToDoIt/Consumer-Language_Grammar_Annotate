"""Bounded direct-engine correction profiling with an exact prediction trace."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from decipher.gloss import load_gloss
from tools.profile_gloss import ProfiledGlossLearner, ProfileTimeout, deadline, file_hash, git_identity, peak_rss


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train',required=True)
    parser.add_argument('--dev',required=True)
    parser.add_argument('--seed-sentences',type=int,default=3000)
    parser.add_argument('--updates',type=int,default=100)
    parser.add_argument('--probes',type=int,default=5)
    parser.add_argument('--timeout',type=float,default=120)
    parser.add_argument('--output',required=True)
    parser.add_argument('--trace',required=True)
    parser.add_argument('--reference-trace')
    args=parser.parse_args()
    if min(args.seed_sentences,args.updates,args.probes)<1:
        parser.error('Seed/update/probe counts must be positive')
    output,trace=Path(args.output),Path(args.trace)
    if output.exists() or trace.exists():
        parser.error('Choose new artifact paths; baselines are never overwritten')
    output.parent.mkdir(parents=True,exist_ok=True)
    trace.parent.mkdir(parents=True,exist_ok=True)
    report={'status':'running','config':vars(args),'source':git_identity(),
            'inputs':{name:{'path':path,'sha256':file_hash(path)} for name,path in [('training',args.train),('development',args.dev)]}}
    model=None
    stage='parsing'
    try:
        with deadline(args.timeout):
            training,train_stats=load_gloss(args.train,skip_misaligned=True)
            development,dev_stats=load_gloss(args.dev,skip_misaligned=True)
            if len(training)<args.seed_sentences+args.updates:
                raise ValueError('Insufficient aligned training records for seed + update prefix')
            seeds=training[:args.seed_sentences]
            stream=training[args.seed_sentences:args.seed_sentences+args.updates]
            used_sources={item.example.tokens for item in seeds+stream}
            probes=[item for item in development if item.example.tokens not in used_sources][:args.probes]
            if len(probes)<args.probes:
                raise ValueError('Insufficient disjoint probe sources')
            report['dataset']={'seed_sentences':len(seeds),'seed_words':sum(len(s.glosses) for s in seeds),
                               'update_sentences':len(stream),'update_words':sum(len(s.glosses) for s in stream),
                               'probe_sentences':len(probes),'probe_words':sum(len(s.glosses) for s in probes),
                               'training_reader':train_stats,'development_reader':dev_stats,
                               'seed_ids_sha256':hashlib.sha256(json.dumps([x.example.id for x in seeds]).encode()).hexdigest(),
                               'stream_ids_sha256':hashlib.sha256(json.dumps([x.example.id for x in stream]).encode()).hexdigest(),
                               'probe_ids_sha256':hashlib.sha256(json.dumps([x.example.id for x in probes]).encode()).hexdigest()}
            stage='seed fitting'
            model=ProfiledGlossLearner('rules')
            start=time.perf_counter()
            model.fit(seeds)
            report['seed_fit_seconds']=time.perf_counter()-start
            initial_profile=dict(model.profile)
            report['seed_profile']=initial_profile
            durations=[]
            digest=hashlib.sha256()
            stage='online corrections'
            with trace.open('w',encoding='utf-8') as handle:
                def emit(phase,step,item):
                    row={'phase':phase,'step':step,'id':item.example.id,'tokens':list(item.example.tokens),
                         'version':model.version,'prediction':model.predict(item.example)}
                    line=json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n'
                    handle.write(line)
                    digest.update(line.encode('utf-8'))
                for probe in probes:
                    emit('probe',0,probe)
                for step,item in enumerate(stream,1):
                    emit('before_feedback',step,item)
                    # The target is released only after the original trace row.
                    start=time.perf_counter()
                    model.correct(item.example,item.glosses)
                    durations.append(time.perf_counter()-start)
                    emit('after_feedback',step,item)
                    for probe in probes:
                        emit('probe',step,probe)
            report['trace_sha256']=digest.hexdigest()
            report['online_profile']={name:model.profile[name]-initial_profile[name] for name in model.profile}
            ordered=sorted(durations)
            report['correction_seconds']={'values':durations,'total':sum(durations),'median':statistics.median(durations),
                                          'p95':ordered[int((len(ordered)-1)*.95)],'maximum':max(durations)}
            report['model']={'version':model.version,'authoritative_records':len(model.records),
                             'rule_hypotheses':len(model.rule_evidence),'prepared_rules':len(model._rules())}
            if args.reference_trace:
                stage='trace equivalence'
                from itertools import zip_longest
                with trace.open(encoding='utf-8') as actual,Path(args.reference_trace).open(encoding='utf-8') as reference:
                    for i,(a,b) in enumerate(zip_longest(actual,reference),1):
                        if a is None or b is None or json.loads(a)!=json.loads(b):
                            raise AssertionError(f'Trace mismatch at row {i}')
                report['reference_trace']={'sha256':file_hash(args.reference_trace),'exact_match':True}
            stage='checkpoint roundtrip'
            with tempfile.TemporaryDirectory(prefix='gloss-online-engine-') as tmp:
                checkpoint=Path(tmp)/'model.gz'
                model.save(checkpoint)
                restored=ProfiledGlossLearner.load(checkpoint)
                if model.records!=restored.records or model._rules()!=restored._rules() or model.version!=restored.version:
                    raise AssertionError('Reload changed authoritative state or rankings')
                for item in probes:
                    if restored.predict(item.example)!=model.predict(item.example):
                        raise AssertionError('Reload changed probe candidates')
                report['checkpoint_equivalent']=True
            report['status']='complete'
    except ProfileTimeout as exc:
        report.update(status='timed_out',incomplete_stage=stage,error=str(exc))
    except Exception as exc:
        report.update(status='failed',incomplete_stage=stage,error=f'{type(exc).__name__}: {exc}')
    finally:
        report['process_peak_rss_bytes']=peak_rss()
        if model is not None:
            report['final_profile']=dict(model.profile)
        output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({name:report.get(name) for name in ('status','online_profile','trace_sha256','error')},indent=2),flush=True)
    return 0 if report['status']=='complete' else 2


if __name__=='__main__':
    raise SystemExit(main())
