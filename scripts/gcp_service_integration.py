"""One predeclared synthetic B service call, separate from public development."""
from pathlib import Path
import json,time,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT,Settings
from schema_match.files import read_csv,load_schema
from schema_match.matching import build_request,MatchingFailure
from schema_match.provider_routing import run_match
from schema_match.vertex_provider_v1 import ARTIFACTS,load_config,digest
from schema_match.records import json_bytes,now_iso


def main():
    root=ARTIFACTS/'validation';slot=root/'slots/service_B.json';result=root/'results/service_B.json'
    if result.exists():print('Saved integration result exists; additional generation0');return
    if slot.exists():raise RuntimeError('Prior service slot unknown; do not replay')
    if len(list((root/'slots').glob('*.json')))>=6:raise RuntimeError('Migration6 cap reached')
    cfg=load_config();data=read_csv((ROOT/'examples/normal.csv').read_bytes());targets=load_schema()
    plan={'at':now_iso(),'purpose':'one synthetic CSV service B integration, not a public-data evaluation',
        'input_sha256':data.sha256,'source':'examples/normal.csv','wire':build_request(data.columns,targets),
        'config':cfg,'planned_calls':1,'automatic_retries':0}
    plan_path=ARTIFACTS/'service-integration-plan.json'
    with plan_path.open('xb') as h:h.write(json_bytes(plan))
    with slot.open('xb') as h:h.write(json_bytes({'at':now_iso(),'label':'service_B','config_hash':digest(cfg),'wire_hash':digest(plan['wire'])}))
    start=time.perf_counter()
    try:
        items,record=run_match(data.columns,targets,Settings(provider='vertex',project=cfg['project'],location=cfg['location'],model=cfg['model']))
    except MatchingFailure as error:record=error.record
    record['service_integration_total_seconds']=time.perf_counter()-start
    record['synthetic_service_integration_only']=True
    with result.open('xb') as h:h.write(json_bytes(record))
    print(json.dumps({k:record.get(k) for k in ('status','output_validation_passed','model_calls_attempted','usage','model_call_seconds','service_integration_total_seconds','cost')}))


if __name__=='__main__':main()
