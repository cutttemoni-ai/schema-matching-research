"""Real calls only; truth scoring is a separate command run after all requests.

One cold + one warm normal request and warm abbreviated/extra requests per phase.
No result cache, truth, row values or profiles enter the matching client.
"""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT,Settings
from schema_match.files import read_csv,load_schema
from schema_match.matching import MatchingFailure,run_match
from schema_match.azure_vm_provider import AzureVMClient
from schema_match.records import json_bytes,now_iso


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',choices=['before','after'],required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    directory=ROOT / args.output / args.phase
    directory.mkdir(parents=True,exist_ok=False)
    settings=Settings.from_env()
    if settings.provider!='azure_vm':raise ValueError('Benchmark requires the same deployed Azure VM')
    if args.phase=='after':
        settings=replace(settings,matching_preset='compact_v1',azure_vm_transport='rest')
    else:
        # Before the tuning fields were added, Settings has neither field.
        if hasattr(settings,'matching_preset'):
            settings=replace(settings,matching_preset='baseline_v2',azure_vm_transport='cli')
    targets=load_schema()
    summary={'phase':args.phase,'started_at':now_iso(),'model':settings.model,
        'notice':'Development examples, not independent research evaluation. Actual inference, no result cache.',
        'measurements':[]}
    for filename,mode in [('normal.csv','cold'),('normal.csv','warm'),('abbreviated.csv','warm'),('extra_columns.csv','warm')]:
        start=time.perf_counter()
        original=(ROOT/'examples'/filename).read_bytes()
        data=read_csv(original)
        file_seconds=time.perf_counter()-start
        def factory(config):
            client=AzureVMClient(config)
            client.unload_before_request=(mode=='cold')
            return client
        print(f'{args.phase}: {filename} {mode}',flush=True)
        try:
            _,record=run_match(data.columns,targets,settings,client_factory=factory)
        except MatchingFailure as exc:
            record=exc.record
        record.update(file_read_metadata_seconds=file_seconds,
            total_processing_seconds=time.perf_counter()-start,
            input_filename=filename,input_sha256=hashlib.sha256(original).hexdigest(),
            benchmark_mode=mode,synthetic_development_check=True)
        assert original==(ROOT/'examples'/filename).read_bytes()
        path=directory/f'{Path(filename).stem}-{mode}.json'
        path.write_bytes(json_bytes(record))
        summary['measurements'].append({'file':filename,'mode':mode,'record':str(path.relative_to(ROOT)),
            'status':record['status'],'total_seconds':record['total_processing_seconds'],
            'calls_attempted':record['model_calls_attempted'],'usage':record['usage'],'timings':record['timings']})
        (directory/'summary.json').write_bytes(json_bytes(summary))
        print(json.dumps(summary['measurements'][-1],ensure_ascii=False),flush=True)
    summary['finished_at']=now_iso()
    (directory/'summary.json').write_bytes(json_bytes(summary))
    return 0 if all(m['status']=='success' for m in summary['measurements']) else 1


if __name__=='__main__':sys.exit(main())
