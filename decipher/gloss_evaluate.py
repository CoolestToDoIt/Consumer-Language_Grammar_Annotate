"""Offline and prequential source-only gloss evaluation."""
from collections import Counter
from pathlib import Path
import json
from types import SimpleNamespace
from .corpus import TextExample
from .gloss import GlossLearner, lexical_key, load_gloss
from .corpus_evaluate import file_info
from .online import OnlineSession


class GlossMetrics:
    def __init__(self):
        self.counts=Counter()
        self.errors=[]

    def add(self,gold,predictions,model):
        if len(gold.glosses)!=len(predictions):
            raise ValueError('Predictions must align with gold word glosses')
        c=self.counts
        c['sentences']+=1
        right_sentence=True
        grounded=set(model.paradigms)
        for word,target,prediction in zip(gold.example.tokens,gold.glosses,predictions):
            correct=prediction['gloss']==target
            oov=word not in model.lexicon
            c['words']+=1
            c['correct']+=correct
            c['covered']+=prediction['gloss'] is not None
            c['top5_correct']+=any(candidate['gloss']==target for candidate in prediction['candidates'])
            if any(char.isalnum() for char in word):
                c['nonpunct_words']+=1
                c['nonpunct_correct']+=correct
            if oov:
                c['oov_words']+=1
                c['oov_correct']+=correct
                key=lexical_key(target)
                label='grounded_oov' if key and key in grounded else 'ungrounded_or_grammatical_oov'
                c[label+'_words']+=1
                c[label+'_correct']+=correct
            right_sentence &= correct
            if not correct and len(self.errors)<25:
                self.errors.append({'id':gold.example.id,'source_word':word,'expected':target,'predicted':prediction['gloss'],'oov':oov})
        c['correct_sentences']+=right_sentence

    def result(self):
        c=self.counts
        def ratio(a,b):
            return c[a]/c[b] if c[b] else None
        return {'counts':dict(c),'word_accuracy':ratio('correct','words'),'sentence_accuracy':ratio('correct_sentences','sentences'),
                'coverage':ratio('covered','words'),'top5_accuracy':ratio('top5_correct','words'),'oov_accuracy':ratio('oov_correct','oov_words'),
                'nonpunct_accuracy':ratio('nonpunct_correct','nonpunct_words'), 'grounded_oov_accuracy':ratio('grounded_oov_correct','grounded_oov_words'),
                'errors':self.errors}


def prepare(train_path,eval_path):
    training,train_stats=load_gloss(train_path,skip_misaligned=True)
    evaluation,eval_stats=load_gloss(eval_path,skip_misaligned=True)
    sources={item.example.tokens for item in training}
    probes=[item for item in evaluation if item.example.tokens not in sources]
    if not training or not probes:
        raise ValueError('Need nonempty training and nonoverlapping evaluation sets')
    return training,probes,{'training_reader':train_stats,'evaluation_reader':eval_stats,'source_overlaps_excluded':len(evaluation)-len(probes)}


def evaluate_gloss(train_path,eval_path,output,split='dev',max_rules=512):
    if split not in ('dev','test'):
        raise ValueError('split must be dev or test')
    training,probes,filters=prepare(train_path,eval_path)
    models={name:GlossLearner(name,max_rules) for name in ('memory','analogy','rules')}
    for model in models.values():
        for gold in training:
            model.correct(gold.example,gold.glosses)
    results={}
    for name,model in models.items():
        metric=GlossMetrics()
        for gold in probes:
            metric.add(gold,model.predict(gold.example),model)
        results[name]={**metric.result(),'rules_considered':len(model._rules())}
    report={'task':'Word-aligned, source-only interlinear gloss prediction; no translations or gold segmentation as input.',
            'split':split,'training':file_info(train_path),'evaluation':file_info(eval_path),'filters':filters,
            'training_sentences':len(training),'training_words':sum(len(g.example.tokens) for g in training),
            'config':{'max_rules':max_rules,'paradigm_window':32,'source_only':True,'gold_segmentation':False,'translation_input':False},'models':results}
    destination=Path(output)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Source-only real-language glossing','',report['task'],'',f"Training sentences: {len(training)}; words: {report['training_words']}. Split: {split}. Excluded sentence-source overlaps: {filters['source_overlaps_excluded']}.",'',
           '| Model | Word exact | OOV word | Grounded lexical OOV | Nonpunctuation word | Sentence exact | Top 5 |','|---|---:|---:|---:|---:|---:|---:|']
    for name,result in results.items():
        def pct(value):
            return 'n/a' if value is None else f'{value:.1%}'
        lines.append('| '+name+' | '+' | '.join(pct(result[key]) for key in ('word_accuracy','oov_accuracy','grounded_oov_accuracy','nonpunct_accuracy','sentence_accuracy','top5_accuracy'))+' |')
    lines += ['', 'Inputs contain only whitespace-delimited source words. Translation, morphological-segmentation and POS tiers are discarded by the reader. This is a stricter source-only variant of shared-task track 1, not a directly comparable official shared-task score. The pinned data_v2 split differs from the original 2023 release.', '',
              'Rules learn prefix/suffix substitutions within a teacher-grounded lexical paradigm and transfer them to another grounded form. The lexical-paradigm heuristic uses lowercase lexical gloss labels and uppercase grammar conventions; this is a declared linguistic assumption. Rule scores are uncalibrated. Unsupported roots remain unknown. Grounded-OOV diagnostics use lexical labels privately in the scorer; they are never a model input. All denominators and alignment exclusions are in JSON.']
    destination.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    for name,result in results.items():
        print(f"{name}: {result['word_accuracy']:.1%} word exact; OOV {result['oov_accuracy'] if result['oov_accuracy'] is not None else 'n/a'}")
    return report


class GlossAdapter:
    def __init__(self,mode):
        self.learner=GlossLearner(mode)
        self.config=SimpleNamespace(max_source_bytes=100000,max_target_bytes=100000)
        self.version=0

    def predict(self,source,**kwargs):
        predictions=self.learner.predict(TextExample('input',tuple(json.loads(source))))
        return {'text':json.dumps([p['gloss'] for p in predictions],ensure_ascii=False,separators=(',',':')),
                'candidates':[],'recall':False,'version':self.version}

    def correct(self,identifier,source,target):
        changed=self.learner.correct(TextExample(identifier,tuple(json.loads(source))),json.loads(target))
        self.version=self.learner.version
        return changed


def online_gloss(train_path,dev_path,directory,support=10,stream_size=100,delays=(0,5,20),policies=('all',),probe_every=25):
    if support<0 or stream_size<1 or probe_every<1 or any(delay<0 for delay in delays):
        raise ValueError('Invalid stream configuration')
    training,probes,filters=prepare(train_path,dev_path)
    if len(training)<support+stream_size:
        raise ValueError('Not enough aligned training sentences for the requested support/stream sizes')
    seeds,stream=training[:support],training[support:support+stream_size]
    rows=[]
    directory=Path(directory)
    for mode in ('memory','analogy','rules'):
        for delay in delays:
            for policy in policies:
                run_directory=directory/f'{mode}-delay-{delay}-{policy}'
                if run_directory.exists() and any(run_directory.iterdir()):
                    raise ValueError(f'Refusing to overwrite a run: {run_directory}')
                model=GlossAdapter(mode)
                session=OnlineSession(model,Path(train_path).stem)
                def source(item): return json.dumps(item.example.tokens,ensure_ascii=False,separators=(',',':'))
                def target(item): return json.dumps(item.glosses,ensure_ascii=False,separators=(',',':'))
                for item in seeds:
                    session.predict(item.example.id,source(item))
                    session.feedback(item.example.id,target(item))
                def snapshot():
                    metric=GlossMetrics()
                    for item in probes:
                        metric.add(item,model.learner.predict(item.example),model.learner)
                    return {'arrived_sentence_labels':len(session.processed)-support,'scores':metric.result()}
                curve=[snapshot()]
                first=GlossMetrics()
                decisions=0
                for i,item in enumerate(stream,1):
                    # Saved sentence prediction occurs before this teacher answer.
                    prediction=session.predict(item.example.id,source(item))
                    glosses=json.loads(prediction['text'])
                    records=[{'gloss':gloss,'candidates':[] if gloss is None else [{'gloss':gloss}]} for gloss in glosses]
                    first.add(item,records,model.learner)
                    decisions+=1
                    if policy=='all' or tuple(glosses)!=item.glosses:
                        session.feedback(item.example.id,target(item),delay=delay)
                    if i%probe_every==0 or i==len(stream):
                        curve.append(snapshot())
                session.export(run_directory)
                model.learner.save(run_directory/'model.json.gz')
                (run_directory/'session.json').write_text(json.dumps(session.state(),ensure_ascii=False,indent=2)+'\n')
                rows.append({'mode':mode,'delay':delay,'policy':policy,'curve':curve,'first_predictions':first.result(),
                             'teacher_decisions':decisions,'pending':len(session.pending),'pending_drained':False})
                print(f"{mode}, delay {delay}, {policy}: {curve[0]['scores']['word_accuracy']:.1%} → {curve[-1]['scores']['word_accuracy']:.1%}",flush=True)
    report={'task':'Source-only real glossing with prediction-before-correction and fixed development probes.',
            'support_sentences':support,'stream_sentences':stream_size,'training':file_info(train_path),'evaluation':file_info(dev_path),
            'filters':filters,'runs':rows}
    (directory/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report
