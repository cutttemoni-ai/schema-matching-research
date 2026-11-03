"""Explicit bounded migration checks. Slots are never replayed automatically."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.vertex_provider_v1 import VertexProvider,ARTIFACTS,load_config,digest
from schema_match.records import json_bytes,now_iso

ROOT=ARTIFACTS/'validation'


def call(label,wire=None):
    ROOT.mkdir(parents=True,exist_ok=True);(ROOT/'slots').mkdir(exist_ok=True);(ROOT/'results').mkdir(exist_ok=True)
    result=ROOT/'results'/f'{label}.json';slot=ROOT/'slots'/f'{label}.json'
    if result.exists():return json.loads(result.read_bytes())|{'loaded_saved_result':True,'additional_inferences':0}
    if slot.exists():raise RuntimeError('Prior slot has no result; investigate SAME slot. No replay.')
    if len(list((ROOT/'slots').glob('*.json')))>=load_config()['migration_inference_cap']:raise RuntimeError('Migration cap6 reached')
    if label!='smoke' and wire is None:raise ValueError('Frozen wire required')
    with slot.open('xb') as h:h.write(json_bytes({'at':now_iso(),'label':label,'config_hash':digest(load_config()),'wire_hash':digest(wire),'automatic_retries':0}))
    provider=None
    try:
        provider=VertexProvider()
        record=provider.generate('Return JSON with ok equal to true.',{'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False},
            system='Return the requested JSON object only.',max_output=1024) if label=='smoke' else provider.run(wire)
    except Exception as error:
        record={'status':'failed','phase':'authentication_or_count_tokens','model_calls_attempted':0,'error_type':type(error).__name__,
            'http_code':getattr(error,'code',None),'error':str(error)[:2000],'at':now_iso()}
    finally:
        if provider:provider.close()
    with result.open('xb') as h:h.write(json_bytes(record))
    return record


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['smoke','develop','status']);args=parser.parse_args()
    if args.command=='smoke':records=[call('smoke')]
    elif args.command=='develop':
        plan=json.loads((ARTIFACTS/'development-plan.json').read_bytes())
        records=[call(method,plan['wires'][method]) for method in 'BCD']
    else:records=[json.loads(p.read_bytes()) for p in sorted((ROOT/'results').glob('*.json'))]
    for r in records:print(json.dumps({k:r.get(k) for k in ('status','phase','model_id','project','location','model_calls_attempted',
        'output_validation_passed','raw_response','usage','model_call_seconds','cost','http_code','error','loaded_saved_result')},ensure_ascii=False))


if __name__=='__main__':main()
