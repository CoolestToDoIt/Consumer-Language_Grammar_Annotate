"""Compare complete engine outputs against a local Git revision.

Uses direct learner calls, not production evaluation. The reference source is
executed from trusted local Git history without switching the working tree.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import types

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from decipher.gloss import GlossLearner,load_gloss
from tools.profile_gloss import deadline,file_hash,git_identity,peak_rss


def reference_engine(revision):
    revision=subprocess.check_output(['git','rev-parse','--verify','--end-of-options',f'{revision}^{{commit}}'],cwd=ROOT,text=True).strip()
    source=subprocess.check_output(['git','show',f'{revision}:decipher/gloss.py'],cwd=ROOT)
    module=types.ModuleType('decipher._comparison_reference')
    module.__package__='decipher'
    sys.modules[module.__name__]=module
    exec(compile(source,'reference_gloss.py','exec'),module.__dict__)
    return module,hashlib.sha256(source).hexdigest(),revision


def compare_state(reference,current):
    # Cross-module dataclass identities differ, so compare their public fields.
    def records(model):
        return [(key,item.example,item.glosses) for key,item in model.records.items()]
    if records(reference)!=records(current) or reference.version!=current.version:
        raise AssertionError('Authoritative records/order or versions differ')
    for name in ('lexicon','paradigms','rule_evidence'):
        if getattr(reference,name)!=getattr(current,name):
            raise AssertionError(f'Learned {name} differs')
    if reference._rules()!=current._rules():
        raise AssertionError('Ordered selected rules differ')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-ref',required=True,help='Trusted local Git revision containing decipher/gloss.py')
    parser.add_argument('--train',required=True)
    parser.add_argument('--dev',required=True)
    parser.add_argument('--limit-train',type=int,default=500)
    parser.add_argument('--limit-dev',type=int,default=30)
    parser.add_argument('--online-updates',type=int,default=0)
    parser.add_argument('--timeout',type=float,default=120)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if min(args.limit_train,args.limit_dev)<1 or args.online_updates<0 or args.timeout<=0:
        parser.error('Limits/timeout must be positive and updates nonnegative')
    output=Path(args.output)
    if output.exists():
        parser.error('Choose a fresh output; comparison reports are never overwritten')
    output.parent.mkdir(parents=True,exist_ok=True)
    report={'status':'running','config':vars(args),'source':git_identity(),
            'environment':{'python':sys.version,'platform':platform.platform()},
            'inputs':{name:{'path':path,'sha256':file_hash(path)} for name,path in [('train',args.train),('development',args.dev)]}}
    stage='reference loading'
    digest=hashlib.sha256()
    rows=0
    try:
        with deadline(args.timeout):
            module,source_hash,revision=reference_engine(args.reference_ref)
            report['reference_engine_sha256']=source_hash
            report['reference_commit']=revision
            stage='corpus selection'
            training,train_stats=load_gloss(args.train,skip_misaligned=True)
            development,dev_stats=load_gloss(args.dev,skip_misaligned=True)
            if len(training)<args.limit_train+args.online_updates:
                raise ValueError('Insufficient training records for requested seed and updates')
            seeds=training[:args.limit_train]
            stream=training[args.limit_train:args.limit_train+args.online_updates]
            used={item.example.tokens for item in seeds+stream}
            probes=[item for item in development if item.example.tokens not in used][:args.limit_dev]
            if not probes:
                raise ValueError('No nonoverlapping development probes')
            report['selection']={'seed_ids':[r.example.id for r in seeds],
                                 'stream_ids':[r.example.id for r in stream],
                                 'probe_ids':[r.example.id for r in probes],
                                 'training_reader':train_stats,'development_reader':dev_stats}
            models={'reference':module.GlossLearner(),'current':GlossLearner()}
            report['fit_seconds']={}
            for name,model in models.items():
                stage=f'{name} fitting'
                start=time.perf_counter()
                if name=='reference' and not hasattr(model,'fit'):
                    for item in seeds:
                        model.correct(item.example,item.glosses)
                else:
                    records=(module.GlossExample(r.example,r.glosses) for r in seeds) if name=='reference' else iter(seeds)
                    model.fit(records)
                report['fit_seconds'][name]=time.perf_counter()-start
            reference,current=models.values()
            compare_state(reference,current)

            def compare_prediction(phase,step,item,mode):
                nonlocal rows
                reference.mode=current.mode=mode
                before=reference.predict(item.example)
                after=current.predict(item.example)
                if before!=after:
                    raise AssertionError(f'Candidate mismatch: {phase}, step {step}, {mode}, {item.example.id}')
                row={'phase':phase,'step':step,'mode':mode,'id':item.example.id,
                     'tokens':item.example.tokens,'version':current.version,'predictions':after}
                digest.update((json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode())
                rows+=1

            stage='complete offline candidates'
            for mode in ('memory','analogy','rules'):
                for item in probes:
                    compare_prediction('offline',0,item,mode)
            stage='online corrections'
            for step,item in enumerate(stream,1):
                for mode in ('memory','analogy','rules'):
                    compare_prediction('before_feedback',step,item,mode)
                reference.correct(item.example,item.glosses)
                current.correct(item.example,item.glosses)
                compare_state(reference,current)
                for mode in ('memory','analogy','rules'):
                    compare_prediction('after_feedback',step,item,mode)
                    for probe in probes:
                        compare_prediction('probe',step,probe,mode)
            report.update(status='complete',exact_match=True,prediction_rows=rows,
                          predictions_sha256=digest.hexdigest(),final_version=current.version,
                          rule_hypotheses=len(current.rule_evidence))
    except Exception as error:
        report.update(status='failed',incomplete_stage=stage,error=f'{type(error).__name__}: {error}')
    finally:
        report['process_peak_rss_bytes']=peak_rss()
        output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report.get(key) for key in ('status','exact_match','prediction_rows','error')},indent=2))
    return 0 if report['status']=='complete' else 2


if __name__=='__main__':
    raise SystemExit(main())
