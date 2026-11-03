"""A: lexical-only baseline. No descriptions, profiles, aliases or LLMs."""
from difflib import SequenceMatcher
import time
import unicodedata

from .models import Recommendation
from .profiles import comparison_rules


def normalize_name(name):
    return ''.join(c for c in unicodedata.normalize('NFKC',name).casefold() if c.isalnum())


def run_baseline(sources,targets,rules=None):
    started=time.perf_counter()
    rules=rules or comparison_rules()[0]
    config=rules['a'];items=[];scores=[]
    for source in sources:
        name=normalize_name(source.name)
        candidates=sorted([{'target_id':target.id,'score':SequenceMatcher(None,name,normalize_name(target.name),autojunk=False).ratio() if name else 0.0}
            for target in targets],key=lambda item:(-item['score'],item['target_id']))
        best=candidates[0] if candidates else None
        if best is None or best['score']<config['no_match_threshold']:
            item=Recommendation(source_id=source.id,target_id=None,status='no_match',reason='이름 유사도가 개발 임계값 미만')
        elif len(candidates)>1 and abs(best['score']-candidates[1]['score'])<=config['tie_epsilon']:
            item=Recommendation(source_id=source.id,target_id=None,status='needs_review',reason='최고 이름 유사도 동률')
        else:item=Recommendation(source_id=source.id,target_id=best['target_id'],status='matched',reason='이름 문자열 유사도 최고 후보')
        items.append(item)
        scores.append({'source_id':source.id,'normalized_name':name,'candidates':candidates})
    return items,{'method':'A','algorithm':config,'candidate_scores':scores,'model_calls_attempted':0,
        'elapsed_seconds':time.perf_counter()-started,'usage':None,'llm_used':False,'status':'success'}
