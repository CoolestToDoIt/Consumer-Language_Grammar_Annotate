"""Source-only interlinear gloss learning from word-aligned teacher answers.

Translation, gold segmentation and POS tiers are never retained as model inputs.
Affix edits reuse a previously grounded lexical meaning; they cannot discover an
ungrounded English meaning from an unfamiliar root.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
import gzip
import heapq
import json
from pathlib import Path
import re
import tempfile
from .corpus import TextExample, nfc


@dataclass(frozen=True)
class GlossExample:
    example: TextExample
    glosses: tuple[str, ...] | None


def load_gloss(path, require_gold=True, skip_misaligned=False):
    """Read SIGMORPHON tiers; discard translation/segmentation at ingestion."""
    records, tiers = [], {}
    stats = {'records_read': 0, 'misaligned': 0, 'missing_gloss': 0}
    def flush():
        if not tiers:
            return
        stats['records_read'] += 1
        number=stats['records_read']
        source=tiers.get('t','').split()
        gloss=tiers.get('g','').split()
        if not source:
            raise ValueError(f'{path}: record {number} has no source words')
        if not gloss and require_gold:
            stats['missing_gloss'] += 1
            raise ValueError(f'{path}: record {number} has no gold gloss')
        if gloss and len(source)!=len(gloss):
            stats['misaligned'] += 1
            if skip_misaligned:
                return
            raise ValueError(f'{path}: record {number}: {len(source)} words / {len(gloss)} glosses')
        records.append(GlossExample(TextExample(f'{Path(path).name}:{number}',tuple(nfc(t) for t in source)),tuple(nfc(g) for g in gloss) if gloss else None))
    with Path(path).open(encoding='utf-8-sig') as handle:
        for raw in handle:
            line=raw.rstrip('\r\n')
            if not line.strip():
                flush(); tiers={}
                continue
            if line.startswith('\\t') or line.startswith('\\g'):
                key=line[1]
                if key in tiers:
                    raise ValueError(f'{path}: repeated \\{key} tier before sentence boundary')
                tiers[key]=line[2:].strip()
            # Deliberately discard \l, \m, \p and other non-source/target tiers.
        flush()
    return records,stats


def majority(counter):
    return min(counter,key=lambda value:(-counter[value],value))


def common_prefix(a,b):
    size=0
    while size<min(len(a),len(b)) and a[size]==b[size]:
        size+=1
    return size


def lexical_key(gloss):
    # Explicit Leipzig-style convention: lowercase lexical labels are anchors;
    # uppercase/digit grammatical tags do not by themselves ground a lexeme.
    return tuple(part for part in re.split('[-=]',gloss) if any(c.islower() for c in part))


def edit(a,b,side):
    shared=common_prefix(a,b) if side=='suffix' else common_prefix(a[::-1],b[::-1])
    if side=='suffix':
        return a[shared:],b[shared:],shared
    return a[:len(a)-shared],b[:len(b)-shared],shared


def transform(value,side,remove,append):
    if side=='suffix':
        if remove and not value.endswith(remove):
            return None
        return (value[:-len(remove)] if remove else value)+append
    if remove and not value.startswith(remove):
        return None
    return append+(value[len(remove):] if remove else value)


class GlossLearner:
    def __init__(self,mode='rules',max_rules=512,paradigm_window=32):
        if mode not in ('memory','analogy','rules'):
            raise ValueError('Gloss model must be memory, analogy, or rules')
        if max_rules<1 or paradigm_window<1:
            raise ValueError('Rule and paradigm bounds must be positive')
        self.mode=mode
        self.max_rules=max_rules
        self.paradigm_window=paradigm_window
        self.records={}
        self.version=0
        self._reset()

    def _reset(self):
        self.lexicon=defaultdict(Counter)
        self.paradigms=defaultdict(list)
        self.rule_evidence=defaultdict(set)
        self._rule_cache=[]
        self._ranked_rules=[]
        self._dirty_rules=set()
        self._rule_index={}
        self._rule_lengths={'prefix':(), 'suffix':()}
        self.grams={}
        self._gram_index=defaultdict(set)

    def _observe(self,record):
        for word,gloss in zip(record.example.tokens,record.glosses):
            self.lexicon[word][gloss]+=1
            if word not in self.grams:
                self.grams[word]=self._grams(word)
                for gram in self.grams[word]:
                    self._gram_index[gram].add(word)
            key=lexical_key(gloss)
            if not key:
                continue
            paradigm=self.paradigms[key]
            if (word,gloss) in paradigm:
                continue
            for other,other_gloss in paradigm[-self.paradigm_window:]:
                if word==other or gloss==other_gloss:
                    continue
                for a,b,ga,gb in ((other,word,other_gloss,gloss),(word,other,gloss,other_gloss)):
                    for source_side in ('prefix','suffix'):
                        remove,append,shared=edit(a,b,source_side)
                        if shared<2 or not (remove or append):
                            continue
                        for target_side in ('prefix','suffix'):
                            remove_gloss,append_gloss,shared_gloss=edit(ga,gb,target_side)
                            if shared_gloss<2 or not (remove_gloss or append_gloss):
                                continue
                            rule=(source_side,remove,append,target_side,remove_gloss,append_gloss)
                            support=self.rule_evidence[rule]
                            if key not in support:
                                support.add(key)
                                self._dirty_rules.add(rule)
            paradigm.append((word,gloss))
        if self._dirty_rules:
            self._rule_cache=None

    def _correct_record(self,example,glosses):
        """Apply one authoritative correction without preparing rule rankings."""
        if not isinstance(example,TextExample) or not example.tokens or not example.id:
            raise ValueError('Corrections need a public example with ID and word tokens')
        glosses=tuple(glosses)
        if len(glosses)!=len(example.tokens) or any(not isinstance(g,str) or not g or any(c.isspace() for c in g) for g in glosses):
            raise ValueError('Glosses must be nonempty labels aligned to source words')
        record=GlossExample(example,glosses)
        previous=self.records.get(example.id)
        if previous==record:
            return False
        if previous is not None and previous.example!=example:
            raise ValueError('A correction ID cannot change source words')
        if previous is None:
            self.records[example.id]=record
            self._observe(record)
        else:
            del self.records[example.id]
            self.records[example.id]=record
            self._reset()
            for item in self.records.values():
                self._observe(item)
        self.version+=1
        return True

    def correct(self,example,glosses):
        changed=self._correct_record(example,glosses)
        if changed:
            self._rules()
        return changed

    def fit(self,records):
        """Apply records in order, preparing inference once at the batch boundary.

        Duplicate and revised annotations behave exactly as successive calls to
        correct(). If the iterable or an annotation fails, earlier successful
        corrections remain applied and their rule cache is prepared before the
        exception propagates. Inference must not run concurrently with fitting.
        """
        try:
            for record in records:
                if not isinstance(record,GlossExample):
                    raise TypeError('fit accepts an iterable of GlossExample records')
                self._correct_record(record.example,record.glosses)
        finally:
            self._rules()
        return self

    def _rules(self):
        if self._rule_cache is None:
            # During append-only ingestion support can only grow. An unchanged
            # outsider cannot overtake the previous top K; only changed rules
            # need to compete with those winners. Revisions reset both sets.
            candidates=set(self._ranked_rules)|self._dirty_rules
            key=lambda rule:(-len(self.rule_evidence[rule]),sum(len(value) for value in (rule[1],rule[2],rule[4],rule[5])),rule)
            # Keep bounded selection exact; sorting is cheaper for small unions.
            if len(candidates)>4*self.max_rules:
                self._rule_cache=heapq.nsmallest(self.max_rules,candidates,key=key)
            else:
                self._rule_cache=sorted(candidates,key=key)[:self.max_rules]
            self._ranked_rules=list(self._rule_cache)
            self._dirty_rules.clear()
            index=defaultdict(list)
            for position,rule in enumerate(self._rule_cache):
                # Inverting the source edit requires its appended affix.
                index[(rule[0],rule[2])].append((position,rule))
            self._rule_index=dict(index)
            self._rule_lengths={side:tuple(sorted({len(affix) for kind,affix in index if kind==side}))
                                for side in ('prefix','suffix')}
        return self._rule_cache

    def _matching_rules(self,word):
        matches=[]
        for side,sizes in self._rule_lengths.items():
            for size in sizes:
                if size>len(word):
                    break
                affix=word[:size] if side=='prefix' else word[len(word)-size:]
                matches.extend(self._rule_index.get((side,affix),()))
        # Retain the original accumulation order, including floating scores
        # and the last supporting rule recorded as candidate evidence.
        return [rule for _,rule in sorted(matches)]

    @staticmethod
    def _grams(word):
        padded='^^'+word+'$$'
        return {padded[i:i+3] for i in range(len(padded)-2)}

    def word_candidates(self,word):
        if word in self.lexicon:
            counts=self.lexicon[word]
            total=sum(counts.values())
            return [{'gloss':g,'score':counts[g]/total,'kind':'lexical','anchor':word} for g in sorted(counts,key=lambda g:(-counts[g],g))[:5]]
        if self.mode=='memory' or not self.lexicon:
            return []
        if self.mode=='analogy':
            query=self._grams(word)
            overlap=Counter()
            for gram in query:
                overlap.update(self._gram_index.get(gram,()))
            def similarity(known):
                shared=overlap[known]
                return shared/(len(self.grams[known])+len(query)-shared)
            # A positive-overlap word always outranks every zero-overlap word.
            # If no words overlap, preserve the original lexical tie-break.
            known=min(overlap,key=lambda w:(-similarity(w),w)) if overlap else min(self.lexicon)
            return [{'gloss':majority(self.lexicon[known]),'score':similarity(known),'kind':'analogy','anchor':known}]
        votes=Counter()
        evidence={}
        for rule in self._matching_rules(word):
            source_side,remove,append,target_side,remove_gloss,append_gloss=rule
            base=transform(word,source_side,append,remove)
            if not base or base==word or base not in self.lexicon:
                continue
            for gloss,count in self.lexicon[base].items():
                proposed=transform(gloss,target_side,remove_gloss,append_gloss)
                if not proposed or lexical_key(proposed)!=lexical_key(gloss):
                    continue
                support=len(self.rule_evidence[rule])
                weight=support/(1+.1*(len(remove)+len(append)+len(remove_gloss)+len(append_gloss)))
                votes[proposed]+=weight*(count/sum(self.lexicon[base].values()))
                evidence[proposed]={'kind':'rule','anchor':base,'rule':list(rule),'support_lexemes':support}
        return [{'gloss':g,'score':votes[g],**evidence[g]} for g in sorted(votes,key=lambda g:(-votes[g],g))[:5]]

    def predict(self,example):
        if not isinstance(example,TextExample):
            raise TypeError('Gloss prediction accepts public word tokens only')
        predictions=[]
        for word in example.tokens:
            candidates=self.word_candidates(word)
            predictions.append({'gloss':candidates[0]['gloss'] if candidates else None,'candidates':candidates,'known_form':word in self.lexicon})
        return predictions

    def save(self,path):
        destination=Path(path)
        destination.parent.mkdir(parents=True,exist_ok=True)
        state={'schema_version':1,'mode':self.mode,'max_rules':self.max_rules,'paradigm_window':self.paradigm_window,'version':self.version,
               'records':[{'id':r.example.id,'tokens':list(r.example.tokens),'glosses':list(r.glosses)} for r in self.records.values()]}
        with tempfile.NamedTemporaryFile(dir=destination.parent,delete=False) as handle:
            temporary=Path(handle.name)
        try:
            with gzip.open(temporary,'wt',encoding='utf-8') as handle:
                json.dump(state,handle,ensure_ascii=False)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    @classmethod
    def load(cls,path):
        with gzip.open(path,'rt',encoding='utf-8') as handle:
            state=json.load(handle)
        if state.get('schema_version')!=1:
            raise ValueError('Unsupported gloss checkpoint schema')
        model=cls(state['mode'],state['max_rules'],state['paradigm_window'])
        def records():
            seen=set()
            for row in state['records']:
                if row['id'] in seen:
                    raise ValueError('Duplicate checkpoint annotation ID')
                seen.add(row['id'])
                yield GlossExample(TextExample(row['id'],tuple(row['tokens'])),tuple(row['glosses']))
        model.fit(records())
        model.version=state['version']
        return model
