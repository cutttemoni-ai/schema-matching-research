"""Read-only local audit of frozen inputs and exported pilot artifacts. No Azure calls."""
from collections import Counter
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / name).read_bytes())


def digest(name):
    return sha256((ROOT / name).read_bytes()).hexdigest()


def main():
    checked = {}
    for name in (
        'research-artifacts/t2d-v1/frozen.json',
        'pilot-artifacts/freeze.json',
        'pilot-artifacts/execution-amendment-01.json',
    ):
        files = read(name)['files']
        for filename, expected in files.items():
            actual = digest(filename)
            if actual != expected:
                raise RuntimeError(f'Frozen file changed: {filename}')
        checked[name] = len(files)

    acquisition = read('datasets/wdc_smb/acquisition.json')
    raw_count = 0
    for record in acquisition['inventory']:
        assert digest(record['path']) == record['sha256'], record['path']
        raw_count += 1
    for record in acquisition['files']:
        assert digest(record['archive']) == record['sha256'], record['archive']

    result = read('PILOT_COMPARISON.json')
    rows = result['rows']
    assert len(rows) == 72 and not result['partial']
    assert result['user_edits_used'] is False
    assert len({r['task_id'] for r in rows}) == 6
    assert Counter(r['method'] for r in rows) == dict.fromkeys('ABCD', 18)
    assert Counter(r['condition'] for r in rows) == dict.fromkeys(
        ('original', 'abbreviated', 'opaque'), 24)
    assert len({(r['task_id'], r['condition'], r['method']) for r in rows}) == 72
    llm = [r for r in rows if r['method'] != 'A']
    assert len({r['request_id'] for r in llm}) == 54
    assert all(r['is_resolved'] for r in rows)
    assert Counter(r['category'] for r in llm) == {
        'correct': 8, 'semantic_error': 35, 'format_error': 9, 'model_error': 2}

    frozen_requests = read('pilot-artifacts/requests.json')['jobs']
    assert {r['request_id'] for r in llm} == {j['request_id'] for j in frozen_requests}
    assert all(r['inference_count'] == 1 for r in llm)
    progress = read('pilot-artifacts/progress.json')
    assert all(progress[k] == 54 for k in (
        'planned', 'reserved', 'submitted_confirmed', 'resolved_results',
        'actual_model_calls_confirmed'))
    assert all(progress[k] == 0 for k in (
        'uncertain', 'in_progress', 'unexecuted', 'remaining_jobs',
        'automatic_inference_retries'))

    with (ROOT / 'PILOT_COMPARISON.csv').open(encoding='utf-8-sig', newline='') as handle:
        exported = list(csv.DictReader(handle))
    assert len(exported) == len(rows)
    for json_row, csv_row in zip(rows, exported):
        for field in ('job_id', 'task_id', 'condition', 'method', 'category',
                      'correct', 'raw_response', 'raw_target_id', 'raw_status',
                      'input_tokens', 'output_tokens', 'cached_input_tokens',
                      'server_model_total_seconds', 'local_total_seconds'):
            expected = '' if json_row.get(field) is None else str(json_row[field])
            assert csv_row[field] == expected, (json_row['job_id'], field)

    integrity = read('pilot-artifacts/completion-integrity.json')
    assert all(integrity[k] for k in (
        'local_first_recommendations_unchanged', 'execution_order_matches_frozen',
        'no_worker_overlap'))
    assert integrity['remote']['all_integrity_checks']
    assert integrity['remote']['expected_digest_matches']
    assert integrity['remote']['chat_post_attempts'] == 54
    assert integrity['remote']['journal_chat_count'] == 54
    assert integrity['remote']['full_http_responses'] == 53
    assert len(list((ROOT/'runs/public_t2d_v3/minimum/slots').glob('*.json'))) == 54
    assert not (ROOT/'runs/public_t2d_v3/extension').exists()
    shutdown = read('pilot-artifacts/shutdown-final.json')
    assert shutdown == {'status': 'Enabled', 'time': '1400', 'timeZoneId': 'UTC'}

    exports = [
        'PILOT_PLAN.md', 'PILOT_RESULTS.md', 'PILOT_COMPARISON.json',
        'PILOT_COMPARISON.csv', 'README.md', 'VALIDATION.md', 'EXPERIMENT_PROTOCOL.md',
        'pilot-artifacts/analysis-facts.json', 'pilot-artifacts/final-summary.md',
        'pilot-artifacts/final-interpretation.md', 'pilot-artifacts/final-evaluation.json',
        'pilot-artifacts/final-evaluation-before-posthoc-resolution.json',
        'pilot-artifacts/group-results.csv', 'pilot-artifacts/method-comparisons.csv',
        'pilot-artifacts/header-comparisons.csv', 'pilot-artifacts/comparisons.json',
        'pilot-artifacts/errors.json', 'pilot-artifacts/progress.json',
        'pilot-artifacts/completion-integrity.json',
        'pilot-artifacts/server-timing-coverage.json', 'pilot-artifacts/unassessed-scope.json',
        'pilot-artifacts/final-candidate-rank-audit.json',
        'pilot-artifacts/output-contract-audit.json',
        'pilot-artifacts/incident-44-local-checkpoint/recovery.json',
        'pilot-artifacts/vm-final.json', 'pilot-artifacts/shutdown-final.json',
        'validation-artifacts/pilot-final-tests.txt',
        'scripts/write_pilot_results.py', 'scripts/assemble_pilot_comparison.py',
        'scripts/audit_pilot_completion.py', 'scripts/verify_pilot_artifacts.py',
    ]
    manifest = {
        'at': datetime.now(timezone.utc).isoformat(),
        'frozen_file_checks': checked,
        'original_dataset_inventory_hashes_checked': raw_count,
        'archive_hashes_checked': len(acquisition['files']),
        'comparison_rows': 72, 'new_model_requests': 54,
        'automatic_inference_retries': 0, 'extension_requests': 0,
        'all_checks_passed': True,
        'network_calls_by_this_verifier': 0,
        'files': {name: digest(name) for name in exports},
    }
    (ROOT/'pilot-artifacts/final-manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in manifest.items() if k != 'files'}))


if __name__ == '__main__':
    main()
