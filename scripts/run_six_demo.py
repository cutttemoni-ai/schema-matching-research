"""One authorized frozen suite, at most 18 real requests, no automatic retry."""
import json
import sys
import time
from datetime import datetime,timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.comparison import prepare_comparison,execute_comparison
from schema_match.config import ROOT,Settings
from schema_match.files import read_csv,load_schema
from schema_match.models import Column
from schema_match.records import json_bytes,now_iso
from schema_match.six_demo import verify_frozen,reserve_slot,evaluate_batch,write_results
from hashlib import sha256

def main():
    frozen=json.loads((ROOT/'demo_cases/six_v1/frozen.json').read_text(encoding='utf-8'))
    verify_frozen(frozen)
    settings=Settings.from_env()
    if settings.__dict__!=frozen['settings']:raise SystemExit('고정 설정과 다릅니다.')
    if settings.provider!='azure_vm':raise SystemExit('기존 Azure VM만 사용합니다.')
    metadata=json.loads((ROOT/'demo_cases/six_v1/metadata.json').read_text(encoding='utf-8'))
    plans={};read_times={};targets=load_schema()
    for case in metadata['cases']:
        at=time.perf_counter();data=read_csv((ROOT/case['input_path']).read_bytes());data.columns=[Column.model_validate(case['source'])]
        read_times[case['case_id']]=time.perf_counter()-at
        plans[case['case_id']]=prepare_comparison(data,targets,settings,['src_001'])
    if len(plans)!=6 or any(p['bcd_blocked_together'] for p in plans.values()):raise SystemExit('6개 계획 사전 검사 실패. 호출 없음.')
    # Persistent lease refuses all reruns, including uncertain interrupted requests.
    lease=ROOT/'runs/six_demo_v1';lease.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory=ROOT/'validation-artifacts/six-demo'/stamp
    with (lease/'lease.json').open('xb') as handle:handle.write(json_bytes({'started_at':now_iso(),'batch_path':str(directory),'max_calls':18}))
    directory.mkdir(parents=True)
    batch={'version':'six-development-v1','started_at':now_iso(),'frozen':frozen,'metadata':metadata,'results':{},'completed':False,'automatic_retries':0}
    start=time.perf_counter()
    for case in metadata['cases']:
        identifier=case['case_id'];verify_frozen(frozen)
        def progress(method,source_id,index,status):
            if index!=0:raise RuntimeError('이 프로토콜은 재시도하지 않습니다.')
            if status=='running':reserve_slot(lease/'slots',identifier,method)
            with (directory/'events.jsonl').open('a',encoding='utf-8') as handle:handle.write(json.dumps({'at':now_iso(),'case_id':identifier,'method':method,'status':status},ensure_ascii=False)+'\n')
            print(f'{now_iso()} {identifier} {method} {status}',flush=True)
        result=execute_comparison(plans[identifier],settings,on_progress=progress,method_order=tuple(case['method_order']))
        result['file_parse_metadata_seconds']=read_times[identifier]
        batch['results'][identifier]=result
        (directory/f'{identifier}.json').write_bytes(json_bytes(result))
        (directory/'partial.json').write_bytes(json_bytes(batch))
    batch['finished_at']=now_iso();batch['elapsed_seconds']=time.perf_counter()-start+sum(p['prepare_seconds'] for p in plans.values())+sum(read_times.values())
    batch['evaluation']=evaluate_batch(batch)
    batch['completed']=True
    (directory/'batch.json').write_bytes(json_bytes(batch))
    write_results(batch,directory)
    pointer={'batch_path':str((directory/'batch.json').relative_to(ROOT)).replace('\\','/'),'sha256':sha256((directory/'batch.json').read_bytes()).hexdigest()}
    (ROOT/'demo_cases/six_v1/saved_result.json').write_bytes(json_bytes(pointer))
    print(json.dumps({'completed':True,'directory':str(directory),'totals':batch['evaluation']['totals'],'helpful_case':batch['evaluation']['helpful_case']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
