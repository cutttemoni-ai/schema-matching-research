"""Stop-only migration checkpoint: observe/fetch existing slots, never submit."""
import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import small_public_v3 as study
from schema_match.remote_jobs_v3 import RemoteJobs
from schema_match.config import Settings
from schema_match.records import now_iso,json_bytes


def main():
    plan=study.read(study.OUT/'small-plan.json');client=RemoteJobs(Settings.from_env())
    report={'started_at':now_iso(),'reason':'User requested migration; no Azure inference submissions',
            'new_inferences':0,'existing_jobs':[]}
    try:
        for job in plan['jobs']:
            slot=study.JOURNAL/'slots'/f"{job['job_id']}.json";result=study.JOURNAL/'results'/f"{job['job_id']}.json"
            if not slot.exists():continue
            if result.exists():continue
            identifier=job['request_id'];entry={'request_id':identifier,'job_id':job['job_id']};report['existing_jobs'].append(entry)
            state=client.status(identifier);entry['first_remote_state']=state
            deadline=time.monotonic()+480
            while not state.get('manifest') and state['state'] in ('running','reserved') and time.monotonic()<deadline:
                state=client.status(identifier)
            entry['last_remote_state']=state
            if state.get('manifest'):
                envelope,manifest=client.fetch(identifier,known_status=state)
                entry.update(recovered=True,remote_state=envelope['state'],inference_count=envelope['inference_count'])
                record=study.finalize_record(job,envelope,manifest,study.read(slot));study.immutable(result,record)
            else:entry.update(recovered=False,requires_followup=True)
        report['active_after_drain']=client.rpc({'operation':'active'})
    finally:
        client.close();report['finished_at']=now_iso();report['progress']=study.progress()
        (study.OUT/'azure-migration-drain.json').write_bytes(json_bytes(report))
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
