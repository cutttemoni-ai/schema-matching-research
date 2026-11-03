"""Resume exactly the previously sealed BCD campaign; never create other IDs."""
import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match import final_study_v2 as study
from schema_match.records import json_bytes,now_iso
from scripts.verify_final_study_v2 import verify_files


def main():
    out=ROOT/'evaluation-artifacts/v3';study.verify_seal()
    acquisition=study.read(ROOT/'datasets/wdc_smb/acquisition.json')
    verify_files({v['path']:v['sha256'] for v in acquisition['inventory']},ROOT)
    metadata=study.read(out/'guest-before-compatibility.json')
    assert metadata['active'] is None and metadata['generation_calls']==0
    assert all(s['state']=='not_found' for s in metadata['states'])
    entry={'started_at':now_iso(),'started_epoch':time.time(),'max_new_inferences':3,'automatic_inference_retries':0}
    try:entry.update(study.execute_compatibility())
    except Exception as error:
        entry.update(error_type=type(error).__name__,error=str(error));raise
    finally:
        entry.update(finished_at=now_iso(),status=study.compatibility_status())
        study.immutable(out/('compatibility-invocation-'+str(time.time_ns())+'.json'),entry)
        print(json.dumps({'confirmed_inferences':entry['status']['confirmed_inferences'],
            'validation_passed':entry['status']['validation_passed'],'states':[(r['method'],r['state']) for r in entry['status']['rows']]}),flush=True)


if __name__=='__main__':main()
