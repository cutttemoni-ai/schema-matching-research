"""Offline scorer only. No cloud client or inference construction."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.small_evaluation_v3 import write_results


if __name__=='__main__':
    result=write_results()
    print(json.dumps({'partial':result['partial'],'rows':len(result['rows']),'planned_llm':result['planned_llm'],
        'groups':[{'method':g['method'],'condition':g['condition'],'correct':g['correct'],'planned':g['planned']} for g in result['groups']]}))
