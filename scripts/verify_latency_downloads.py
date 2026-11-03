"""Validate real browser downloads after the explicitly agent-operated UI test."""
import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.files import read_csv,load_schema
from schema_match.records import json_bytes,now_iso


def main():
    directory=ROOT/'validation-artifacts/latency-browser'
    state=json.loads((directory/'ui-validation.json').read_text(encoding='utf-8'))
    final_path=max((ROOT/'runs/user_final').glob('*.json'),key=lambda p:p.stat().st_mtime_ns)
    final=json.loads(final_path.read_text(encoding='utf-8'))
    initial_path=ROOT/final['initial_ai_record']
    initial_bytes=initial_path.read_bytes()
    assert initial_bytes==(directory/'ai-before-review.json').read_bytes()
    initial=json.loads(initial_bytes)
    assert initial['provider']=='azure_vm' and initial['prompt_version']=='B-v3-compact'
    assert initial['status']=='success' and final['ai_executed'] is True
    data=read_csv((ROOT/'examples/normal.csv').read_bytes())
    targets=load_schema()
    paths={item['kind']:Path(item['path']) for item in state['downloads']}
    outputs={name:path.read_bytes() for name,path in paths.items()}
    parsed={name:list(csv.reader(io.StringIO(content.decode('utf-8-sig')))) for name,content in outputs.items()}
    choices={r['source_id']:r['final_target_id'] for r in final['mappings']}
    assert choices['src_002'] is None
    original_product_name=next(r for r in final['mappings'] if r['source_id']=='src_002')
    assert original_product_name['ai_target_id']=='product_name' and original_product_name['changed_from_ai'] is True
    for col in data.columns:
        target=choices[col.id]
        rows=parsed['standardized'] if target else parsed['unmapped']
        header=next(t.name for t in targets if t.id==target) if target else col.name
        assert [row[rows[0].index(header)] for row in rows[1:]]==data.frame[col.name].tolist()
    assert [row[parsed['standardized'][0].index('product_code')] for row in parsed['standardized'][1:]]==['00124','00007','00981']
    assert len(parsed['mapping'])==7
    after_records=list((ROOT/'runs/ai_initial').glob('*.json'))
    assert len(after_records)==state['ai_record_count_after_recommendation']
    additional=[]
    finished=datetime.fromisoformat(initial['finished_at'])
    for kind in ['ai_initial','ai_failure','smoke']:
        for path in (ROOT/'runs'/kind).glob('*.json'):
            record=json.loads(path.read_text(encoding='utf-8'))
            if record.get('started_at') and datetime.fromisoformat(record['started_at'])>finished:
                additional.append(str(path.relative_to(ROOT)))
    assert not additional
    for kind,content in outputs.items():(directory/f'{kind}.csv').write_bytes(content)
    (directory/'user-final.json').write_bytes(final_path.read_bytes())
    state.update(verified_at=now_iso(),actor='agent_browser_validation_not_independent_human_research',
        all_download_cell_strings_preserved=True,leading_zeros_preserved=True,initial_ai_unchanged=True,
        initial_ai_path=str(initial_path.relative_to(ROOT)),user_final_path=str(final_path.relative_to(ROOT)),
        model_calls_during_review_and_download=0,
        additional_call_records_after_recommendation=additional,
        initial_ai_sha256=hashlib.sha256(initial_bytes).hexdigest(),app_wait_to_record_seconds=initial.get('app_wait_to_record_seconds'))
    (directory/'verification.json').write_bytes(json_bytes(state))
    print(json.dumps({k:v for k,v in state.items() if k!='downloads'},ensure_ascii=True,indent=2))


if __name__=='__main__':main()
