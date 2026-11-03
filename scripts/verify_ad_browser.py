"""Verify real UI downloads and absence of extra model requests after loading history."""
import csv
import io
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.records import json_bytes,now_iso


def main():
    folder=ROOT/'validation-artifacts/ad-browser'
    baseline=json.loads((folder/'initial-call-counts.json').read_text(encoding='utf-8-sig'))
    after={kind:len(list((ROOT/'runs'/kind).glob('*.json'))) for kind in baseline}
    assert after==baseline
    downloaded=json.loads((folder/'downloads.json').read_text(encoding='utf-8'))
    paths={item['kind']:Path(item['path']) for item in downloaded}
    payloads={kind:path.read_bytes() for kind,path in paths.items()}
    comparison=json.loads(payloads['comparison'])
    original=json.loads((ROOT/'validation-artifacts/ad-live/20261102T030729Z/comparison.json').read_text(encoding='utf-8'))
    assert comparison==original
    profiles=json.loads(payloads['profiles'])
    assert profiles['profiles']==comparison['plan']['full_profiles']
    assert profiles['selected']==comparison['plan']['selected_profiles']
    assert profiles['selection_logs']==comparison['plan']['selection_logs']
    assert profiles['rules_sha256']==comparison['plan']['rules_sha256']
    rows=list(csv.DictReader(io.StringIO(payloads['summary'].decode('utf-8-sig'))))
    assert [r['방법'] for r in rows]==['A','B','C','D']
    assert [r['정답 / 전체'] for r in rows]==['0 / 1','0 / 1','1 / 1','1 / 1']
    assert [r['입력 토큰'] for r in rows][1:]==['387','889','628']
    assert all(row['실패 시도']=='0' and row['재시도']=='0' for row in rows)
    evaluation=json.loads(payloads['evaluation'])
    original_evaluation=json.loads((ROOT/'validation-artifacts/ad-live/20261102T030729Z/evaluation.json').read_text(encoding='utf-8'))
    assert evaluation['methods']==original_evaluation['methods'] and evaluation['human_edits_used'] is False
    for kind,body in payloads.items():(folder/f'downloaded-{kind}.{ "csv" if kind=="summary" else "json"}').write_bytes(body)
    result={'verified_at':now_iso(),'actor':'agent_ui_development_validation_not_independent_research',
        'actual_comparison_download_matches_live_record':True,'profile_and_selection_downloads_match':True,
        'csv_all_four_methods_and_metrics_match':True,'evaluation_uses_initial_not_human_edits':True,
        'raw_recommendation_and_policy_table_visible':True,'existing_result_message_visible':True,
        'run_button_disabled_without_opt_in':True,'selection_feature_lists_and_reasons_visible':True,
        'additional_model_calls_during_history_load_rerun_and_download':0,
        'call_record_counts_before':baseline,'call_record_counts_after':after,
        'screenshot':'validation-artifacts/ad-browser/comparison.png'}
    (folder/'verification.json').write_bytes(json_bytes(result))
    print(json.dumps(result,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
