"""Durable first-attempt reservations; never repeat an uncertain remote call."""
import json
from pathlib import Path
from .records import json_bytes,now_iso

def reserve_job(directory,job):
    slots=Path(directory)/'slots';slots.mkdir(parents=True,exist_ok=True)
    path=slots/(job['job_id']+'.json')
    with path.open('xb') as handle:handle.write(json_bytes({'job_id':job['job_id'],'reserved_at':now_iso(),
        'request_sha256':job['request_sha256'],'retry_count':0}))
    return path

def job_state(directory,job_id):
    root=Path(directory);result=root/'results'/f'{job_id}.json';slot=root/'slots'/f'{job_id}.json'
    if result.exists():return 'completed'
    if slot.exists():return 'reserved_without_result_do_not_repeat'
    return 'pending'
