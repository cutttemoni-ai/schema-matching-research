"""Load local comparison records only when their input/settings still match."""
import json
from .config import ROOT


def compatible_result(result,data,targets,settings,source_ids,rules_sha256):
    if result.get('kind')!='developer_comparison':return False
    plan=result.get('plan',{})
    lookup={c.id:c.model_dump() for c in data.columns}
    return (plan.get('input_sha256')==data.sha256 and plan.get('rules_sha256')==rules_sha256
        and plan.get('settings')==settings.__dict__
        and plan.get('sources')==[lookup.get(identifier) for identifier in source_ids]
        and plan.get('targets')==[c.model_dump() for c in targets])


def saved_comparisons(data,targets,settings,source_ids,rules_sha256):
    folder=ROOT/'runs/comparison'
    paths=sorted(folder.glob('*.json'),key=lambda path:path.stat().st_mtime_ns,reverse=True)[:50]
    results={}
    for path in paths:
        try:
            result=json.loads(path.read_text(encoding='utf-8'))
            if compatible_result(result,data,targets,settings,source_ids,rules_sha256):
                result['record_path']=str(path)
                label=f"{result['started_at']} · {result['run_id'][:8]} · 재시도 {result['retry_invocations']} · {path.stem[:6]}"
                results[label]=result
        except (ValueError,OSError,KeyError,TypeError):continue
    return results
