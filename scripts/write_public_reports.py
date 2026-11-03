"""Local reports from real acquisition/audit/dry-run/first-attempt evidence."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.records import json_bytes,now_iso

OUTPUT=ROOT/'research-artifacts/t2d-v1'

def main():
    acquisition=json.loads((ROOT/'datasets/wdc_smb/acquisition.json').read_text(encoding='utf-8'))
    audit=json.loads((OUTPUT/'dataset-audit.json').read_text(encoding='utf-8'));dry=json.loads((OUTPUT/'dry-run.json').read_text(encoding='utf-8'))
    frozen=json.loads((OUTPUT/'frozen.json').read_text(encoding='utf-8'));config=json.loads((ROOT/'config/research_t2d_v1.json').read_text(encoding='utf-8'))
    lines=['# T2D-SM-WH 실제 데이터 감사','',f"감사: {audit['audited_at']} (UTC). 다운로드: {acquisition['downloaded_at']} (UTC).",
        '', '## 출처·파일·이용 조건','',
        '공식 출처: https://webdatacommons.org/structureddata/smb/ . 공식 페이지 HTML의 실제 링크를 파싱해 내려받았으며 주소를 추측하지 않았다. GitHub 링크의 HTTP 리디렉션은 acquisition.json에 보존했다. 실제 다운로드는 모두 HTTP200이었다. 웹 읽기 도구는 ZIP을 텍스트로 표시하지 못했지만 Python 다운로드는 성공했으며 대체/합성 데이터로 대체하지 않았다.',
        '', '| 파일 | 실제 바이트 | SHA-256 |','|---|---:|---|']
    for item in acquisition['files']:lines.append(f"| {Path(item['archive']).name} | {item['bytes']} | `{item['sha256']}` |")
    lines.extend(['', 'ZIP 원본과 압축 해제 파일은 datasets/wdc_smb/raw/에 보존한다. 원본을 덮어쓰거나 CSV 헤더·값을 수정하지 않았다. 각 파일의 경로·크기·SHA-256 전체 목록은 datasets/wdc_smb/acquisition.json에 있다. 원문 HTML도 보존했다.',
        '공식 저장소 LICENSE(https://github.com/wbsg-uni-mannheim/wdc-smb/blob/main/LICENSE)는 BSD-3-Clause이며 저작권/조건/면책 보존 및 기여자 명의의 무단 보증 금지 조건을 담고 있다. 사본은 raw/repository-LICENSE.txt에 저장했다. 아카이브별 별도 라이선스 문서와 원천 Web 페이지·DBpedia 데이터의 개별 권리 범위는 이 감사에서 확정하지 못했다. 저장소 라이선스를 모든 원천 콘텐츠의 권리 해소나 무제한 상업적 재배포 보장으로 확대하지 않는다. 제출 자료에는 출처·저작권 고지를 유지하고 원본 전체 재배포 여부는 별도 확인한다.',
        '', '## 실제 구조','', '```text','datasets/wdc_smb/raw/', '  t2d_sm_wh.zip', '  t2d_sm_wh/',
        '    train/{webtables/(71 CSV), dbpedia_tables/(71 CSV), train_correspondences.csv}',
        '    valid/{webtables/(18 CSV), dbpedia_tables/(18 CSV), valid_correspondences.csv}',
        '    test/{webtables/(89 CSV), dbpedia_tables/(89 CSV), test_correspondences.csv}',
        '    .ipynb_checkpoints/ 및 split 내부 checkpoint 디렉터리: 실행 입력에서 제외',
        '  t2d_sm_supplement_metadata.zip','  t2d_sm_supplement_metadata/(178 JSON, 하위 경로는 acquisition inventory 참조)',
        '  official-page.html / repository-LICENSE.txt','```',
        '', '아래 수치는 실제 CSV를 csv.reader로 읽어 집계했다. 공식 웹 페이지 수치를 복사해 집계한 것이 아니다.',
        '', '| 공식 분할 | 표 쌍 | 원본/대상 열 | 주석 원본 열 | 양성 | 음성 | 정답 행 | 전체 열 조합 | 미주석 조합 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|'])
    for split,info in audit['splits'].items():
        c=info['counts'];lines.append(f"| {split} | {c['table_pairs']} | {c['web_columns']} / {c['dbpedia_columns']} | {c['annotated_source_columns']} | {c['positive_rows']} | {c['negative_rows']} | {c['raw_annotation_rows']} | {c['cartesian_column_pairs']} | {c['unannotated_cartesian_pairs']} |")
    lines.extend(['', '합계178쌍·356표·원본923열/대상928열(총1,851열), 정답2,642행(양성445/음성2,197), 전체 가능한 열 조합4,994개 중 미주석2,352개다.',
        '', '## 정답 스키마·식별자·주석 범위','',
        '`[빈 열 이름], table_name, column_name_left, column_index_left, column_name_right, column_index_right, label`. 첫 빈 열은 정답 CSV의 내보내기 행 번호이며 표의 열이 아니다. table_name에 .csv를 붙인 동일 파일명이 webtables(원본)와 dbpedia_tables(대상)를 연결한다.',
        '인덱스는 0부터 시작한다. 실제 파일 헤더와 양쪽 인덱스의 이름을 대조한 5,284회 검사가 전부 일치했으며 1-based 해석은 일치0이었다. label=1은 해당 열 쌍의 양성, label=0은 그 열 쌍의 음성이다. label=0 또는 양성 부재가 원본 열 전체의 no_match를 의미하지 않는다.',
        '주석은 전체 Cartesian 후보를 완전 판정하지 않는다. 원본 열마다 모든 대상 열의 주석이 있는 행은 train46/valid23/test55개뿐이다. 미주석 쌍은 unknown으로 유지하고 후보에서 제외한다. GT의 이름 필드는 감사에만 사용하며 모델의 메타데이터는 실제 CSV 헤더에서 읽는다.',
        '', '## 품질 점검','', '| 분할 | 빈 헤더 | 중복 헤더 위치 | 빈 열 | 결측 셀/전체 셀 | 동일 정답 중복 | 충돌 정답 키 |', '|---|---:|---:|---:|---:|---:|---:|'])
    for split,info in audit['splits'].items():
        tables=[t for t in audit['tables'] if t['split']==split];c=info['counts']
        lines.append(f"| {split} | {sum(len(t['empty_header_positions']) for t in tables)} | {sum(len(t['duplicate_header_positions']) for t in tables)} | {sum(len(t['empty_column_positions']) for t in tables)} | {sum(t['missing_cells_strip_empty'] for t in tables)} / {sum(t['total_cells'] for t in tables)} | {c['duplicate_annotation_rows']} | {c['conflicting_pair_label_keys']} |")
    lines.extend(['', '결측은 공백 제거 후 빈 문자열이다. 실제 합계42,652/294,226셀, 빈 열16개이며 NA/null/None/NaN/N/A 표기119개는 원문 문자열로 보존하고 결측으로 임의 변환하지 않았다. 실제 표에서 빈/중복 헤더는0, 파일 파싱 오류0, 인덱스·이름 불일치0이다. 어댑터는 향후 빈/중복 헤더가 있어도 위치로 구분하며 원본 값은 문자열 그대로 보존한다.',
        '동일 열 쌍의 중복 주석과 양/음 충돌은0이나, train에서 두 원본 열이 같은 대상에 양성으로 연결되는 원본 열2개가 있었다. 공식 1:1 가정과 맞지 않아 해당2열을 제외했다. multiple positive/invalid/no annotations 등 제외 내역은 exclusions.jsonl에 별도 저장했다. 파일명·열 위치·제외 사유를 확인할 수 있다.',
        '', '| 분할 | 주 Top-1 문제 | 자연 발생 no_match | 통제 no_match | 제외 사유별 원본 열 수 |', '|---|---:|---:|---:|---|'])
    for split,info in audit['splits'].items():
        c=info['counts'];reason='; '.join(f'{key}: {value}' for key,value in info['excluded_source_columns'].items())
        lines.append(f"| {split} | {c['tasks_main']} | {c['tasks_natural_none']} | {c['tasks_controlled_none']} | {reason} |")
    lines.extend(['', '주 문제443개, 자연 no_match19개(모든 대상의 명시적 음성 확인), 통제 no_match443개(알려진 양성 제거·명시적 음성만 유지)다. 통제 문제는 같은 원본의 변형이며 독립 원본 열 수에 더하지 않는다. 불완전 주석에서 양성 없는385열과 주석 전혀 없는74열을 no_match 정답으로 만들지 않았다.',
        '', '## 설명과 분할·계열 중복','',
        '보조 JSON178개가 모든 표 쌍을 연결한다. 실제 키는 다음과 같다: '+', '.join(sorted(audit['supplement_keys']))+'.',
        '이는 페이지 URL·제목·주변 텍스트·시각·구조 메타데이터이며 구조화된 열별 설명은 제공되지 않는다. 이번 B/C/D의 설명은 양쪽 모두 빈 문자열이다. 주변 페이지 문맥은 제외하며 GT로 설명을 생성하지 않는다. 따라서 설명 제거에 따른 성능 하락은 이 데이터/설정으로 측정할 수 없다.',
        f"분할 사이 동일성/같은 페이지 연결 그룹은 실제8개다(기준별: {dict(Counter(g['basis'] for g in audit['cross_split_duplicate_or_page_groups']))}). 중복 기준들은 중첩될 수 있으므로 그룹 수를 독립 표 수처럼 합산하지 않는다. 파일명만 다른 동일 바이트, 행 순서를 무시한 동일 값 배열, 동일 source URL(쿼리/fragment 제외)을 함께 검사했다.",
        f"이 연결 성분이 train/valid와 겹치는 test 표 쌍은 {audit['test_pairs_quarantined_identity_or_page']}개다. 공식 분할을 이동시키지 않고 test 후보에서 격리한다. 표본 내부에서도 동일 연결 성분은 한 번만 선택한다. 동일 DBpedia 헤더 템플릿의 교차 분할 그룹도 {len(audit['cross_split_dbpedia_header_templates'])}개였으나 이는 다른 행의 같은 스키마일 수 있어 동일 데이터라고 단정하지 않는다.",
        '웹 도메인/토픽은 분할 사이 공유될 수 있다. 행이 부분적으로 겹치는 모든 근접 복제, 원래 DBpedia 질의/클래스·생성 계열의 완전 분리까지 증명하지 못했다. 현재 필터는 식별 가능한 동일 표/원본 페이지 수준의 보수적 격리이며 도메인 외 일반화나 완전 독립 계열 평가라고 주장하지 않는다. 자세한 그룹은 dataset-audit.json의 duplicate_or_family_groups 및 cross_split_dbpedia_header_templates에 있다.',
        '', '## 재현','',
        '획득: scripts/acquire_wdc.py. 원본 감사: scripts/audit_wdc.py. 전체 로컬 점검: scripts/dry_run_wdc.py. 동결 후에는 dry-run이 기존 산출물을 덮어쓰지 않는다. 실행/재개 시 원본 inventory의 모든 해시를 검사한다. 독립 연구 성능 평가 결과는 아직 없다.'])
    (ROOT/'DATASET_AUDIT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    p=['# 공개 데이터 실험 프로토콜 — t2d-annotated-bilateral-v1','',
        '목표: 메타데이터가 불완전할 때 실제 데이터 프로파일이 LLM 스키마 매칭의 정확도·효율에 주는 차이를 공개 T2D-SM-WH에서 분석한다. 합성 결과는 기존 개발 기록으로 유지하며 이 버전과 합산하지 않는다. 이번 단계는 확보·감사·어댑터·전체 로컬 점검·개발 문제 최대3회 연결 확인까지이며 전체 평가 실행은 하지 않는다.',
        f"모델/규칙/표본·요청 동결: {frozen['frozen_at']} UTC, research-artifacts/t2d-v1/frozen.json. 현재 모델 Qwen3:4b, 기존 Azure CPU VM 유지. Google Cloud 전환·신규 유료 리소스 생성 없음.",
        '', '## 과제 정의와 정답','',
        '기본 단위는 한 원본 열과 그 열에 대해 명시적으로 주석된 대상 후보 집합이다. 유일 양성1개와 명시적 음성1개 이상인 집합을 main Top-1로 구성한다. 미주석 쌍은 음성으로 만들지 않고 후보에 넣지 않는다. 따라서 대부분 **주석된 후보 집합 내 Top-1**이며 전체 대상 스키마 매칭 성능이나 원 논문의 이진 correspondence F1과 동일하지 않다. 주석 완전성 여부와 전체 대상 열 수를 각 task에 저장했다.',
        '자연 no_match는 실제 대상 스키마의 모든 열이 명시적 음성인 경우만 인정한다. 통제 no_match는 같은 main 문제에서 알려진 양성 후보를 제거하고 명시적 음성만 남긴 별도 조건이다. 자연/통제 no_match와 main을 별도 지표로 보고한다. 양성 부재 자체를 no_match로 해석하지 않는다.',
        '복수 양성·양/음 충돌·인덱스/헤더 불일치·원본 간 양성 대상 충돌·주석 부재 등은 별도 목록과 건수로 공개한다. 실제 모델 출력의 정답 여부·유사도 점수로 문제를 골라내지 않는다.',
        '', '## A~D와 정보 경계','',
        '| 방법 | 입력 |','|---|---|',
        '| A | 양쪽 이름의 NFKC/casefold/Unicode 영숫자 정규화 + SequenceMatcher(autojunk=False), 임계값0.60, 동률은 검토. 한글 유지, 번역/별칭 없음 |',
        '| B | 양쪽 CSV 열 이름·제공 설명(없어 빈 문자열)·로컬 추정 자료형만 |',
        '| C | B + 양쪽 열에서 계산 가능한 사전 정의 전체 프로파일 |',
        '| D | B + C와 같은 값에서 자료형 기반 선택 프로파일 v0로 선택한 부분집합 |',
        '', '기존 synthetic 비교는 원본 쪽만 프로파일을 전달했다. 이번 **양측 프로파일**은 새 실험 설정이며 기존 수치와 통합하지 않는다. D는 추가 LLM 호출·열 이름·정답·주변 열로 특징을 고르지 않는다. 완전 결측 열에서는 C와 D의 계산 가능 공통 특징이 같을 수 있다.',
        '프로파일 산출식/분모/결측/숫자·날짜 판정은 PROFILE_SPEC.md와 config/comparison_v0.json을 그대로 사용한다. 전체 원본 문자열로 별도 계산하고 원본 CSV/값을 변환하지 않는다. B의 자료형은 기존 files.infer_type의 최대1,000개 비결측 문자열 추정, D의 선택 유형은 전체 프로파일의 inferred_type이며 둘을 동일한 것으로 가정하지 않는다.',
        'C의 top_categories는 실제 범주 문자열을 포함한다. D 문자열 규칙은 이를 제외하므로 C/D 차이는 특징 수와 범주 의미 정보 포함 여부를 함께 반영한다. 전체 원시 행 배열은 전송하지 않는다. 값 문자열을 잘라 C를 D처럼 만들지 않는다.',
        '열 ID는 seed·표 식별자·위치의 SHA-256에서 생성한 s_/t_ 16자리 opaque ID다. 원 정답 파일명/분할/label/정답 이름 목록/expected ID는 wire에 들어가지 않는다. 후보 순서는 seed와 표·원본 위치·대상 위치의 해시로 정하고, label과 무관하며 모든 방법·조건에서 유지한다.',
        'research_data는 정답을 검증하고 truth-free tasks와 별도 answers를 만든다. research_request의 TaskInput에는 정답/표 식별자/분할 필드 자체가 없으며, audit_request는 CSV에서 온 허용 메타데이터/계산된 프로파일과 payload의 정확한 일치를 확인한다. 실제 헤더가 label인 경우는 정당한 메타데이터이며 단순 금칙어 검색으로 삭제하지 않는다. 엔진은 다시 키·ID 형식을 검증한다.',
        '', '## 메타데이터 조건 — 원본 쪽만 변형','',
        '1. original: 원래 헤더. 2. abbreviated: NFKC → 소문자/숫자-대문자 경계 분리 → Unicode 영숫자 토큰 → casefold → 각 토큰 앞3 codepoint를 underscore로 연결(빈 이름은 빈 이름). 3. opaque: column_0001처럼 원본 위치의 의미 없는 ID.',
        '대상 쪽 헤더는 세 조건 모두 원래 이름이다. 이는 양쪽 이름을 지운 공식 T2D-SM-NH와 다르다. 변형으로 값·자료형·프로파일·후보 ID/순서를 바꾸지 않는다. 같은 원본의 모든 변형/통제 조건은 원 공식 분할과 연결 성분에 남는다.',
        '열 설명이 원래 없으므로 설명 제거 효과는 측정 불가다. 한영 혼용·한국 공개 데이터 보조 실험은 미구현 계획이다. 번역·설명 생성은 적용하지 않았으며 별도 실제 데이터/변형 정의/권리 확인 후 새 버전으로 동결해야 한다.',
        '', '## 생성·한도·검증','',
        'B/C/D 공통 모델·후보·시스템 지시·출력 형식·온도0·context8192·2 threads·think=false·keep_alive=-1·출력160. 일반 표용 research-bilateral-v1 지시를 결과 확인 전에 작성·동결했다. 기존 서비스의 상품/주문 전용 프롬프트는 수정하지 않았다.',
        '출력은 source_id, target_id/null, matched/no_match/needs_review, 짧은 근거. Python에서 후보 ID·원본 coverage·상태/null 일관성을 검증한다. 원 모델 JSON과 정책 결과/실패를 구분하고 이름별 강제 규칙은 없다. JSON 유효성이 의미 정답을 보증하지 않는다.',
        'truncate=false/shift=false. 기존 UTF-8 바이트 기반 보수적 예산을 그대로 사용한다(실제 토큰 수가 아님). 초과를 모델 서버가 실제로 거부한 것으로 단정하지 않고 로컬 사전 차단으로 기록한다. 출력 done_reason=length, 서버/전송 제한은 실패다. Run Command 응답 압축3500자/전송4096바이트 규칙과 VM 원문 보존 동작을 유지한다.',
        '주 비교 표본은 세 조건 B/C/D 모두 같은 제한 검사를 통과하는 공통 범위에서 선정한다. 이는 작은 요청 편향을 가진 기술적 부분집합이다. 전체 corpus에서 차단된 건수도 함께 공개한다. 평가 뒤 특징 삭제·후보 축소·몰래 분할·재시도하여 성공으로 바꾸지 않는다. 전체 범위를 넓히려면 명시적인 공통 분할/압축 프로토콜을 새 버전으로 작성해야 한다.',
        '', '## 분할·표본·지표','',
        '공식 train/valid는 파서·프롬프트·규칙 개발용이고 test는 최종 평가용이다. 이번에는 기존 A/D 기준을 조정하지 않았고 test 정확도를 계산하거나 보고 규칙을 바꾸지 않았다. 테스트 파일은 구조·품질·누락/중복·요청 한도 감사를 위해 읽었으며 A 예측은 로컬 산출물로만 저장했다. 이는 test 성능 평가를 마쳤다는 뜻이 아니다.',
        '분할 간 동일 내용/같은 원본 페이지 성분의 test7쌍을 격리했다. seed20261102 SHA 순서, 부족한 자연 no_match 성분 우선 배정, 표 쌍/성분당 원본1열을 선택한다. 난수 seed만 바꾼 변형을 독립 데이터로 세지 않는다. 후보/표본 계획은 plans/*.json에 호출 전에 동결했다. 부분 복제·모든 원천 생성 계열의 완전 분리까지는 미검증이다.',
        'main Top-1 = 유효 matched 및 유일 정답 ID 일치 수 / 모든 예정 main 열. needs_review와 호출/형식 실패는 정답이 아니며 분모에 남긴다. 자연/통제 no_match 정답은 유효 no_match/null, 오연결은 non-null 후보(잠정 대상 포함) 비율이다. 검증 실패 원 출력의 non-null은 별도 진단으로 공개해 정책 거부 후 0을 성공처럼 해석하지 않는다.',
        '검토 필요 비율과 API/형식 실패를 별도로 보고한다. 원/정책 결과·실패·미종료/원격 불명 상태를 보존하고 성공만 골라 집계하지 않는다. 사용자 수정 결과는 평가에 쓰지 않는다. 같은 원본의 방법/조건/반복은 종속된 paired 관측이며 행 수 증가를 독립 표본 증가로 해석하지 않는다. 작은 표본의 일반화·통계적 우위는 주장하지 않는다.',
        '', '## 전체 로컬 dry-run — 모델 호출0','',
        f"실제 {dry['tables_parsed']}표·{dry['columns_profiled']}열 전체를 파싱·프로파일 처리했고 A {dry['a_runs']}건과 B/C/D 요청 {dry['bcd_requests_generated']}건을 생성했다. 수행 {dry['elapsed_seconds']:.3f}초. 실패 파싱0. 이 수는 main/자연/통제 문제와 세 이름 조건의 조합이며 독립 원본 수가 아니다.",
        '', '| 방법 | 생성 요청 | 예산 통과 | 사전 차단 |','|---|---:|---:|---:|']
    for method in ('B','C','D'):
        passed=sum(c['count'] for c in dry['preflight_counts'] if c['method']==method and c['status']=='pass')
        blocked=sum(c['count'] for c in dry['preflight_counts'] if c['method']==method and c['status']=='blocked')
        p.append(f'| {method} | {passed+blocked} | {passed} | {blocked} |')
    p.extend(['', f"누수 격리 후 세 조건 공통 기술 범위의 test 문제 수: {dry['nonleaking_test_common_feasible_tasks']}. 원래 전체 test209개 main 중 공통 범위48개라는 범위 제한을 공개한다. 모든 요청/감사는 dry-requests.jsonl.gz, A는 dry-a-results.jsonl.gz, 열별 특징은 column-features.json.gz, 차단 목록은 task-registry.jsonl.gz에 있다.",
        '', '## 제안 규모 — 아직 실제 실행하지 않음','', '| 안 | 표 쌍 | 원본 열 | 통제 포함 과제 변형 | 이름 조건 | 반복 | A 로컬 | 실제 LLM 예정 |', '|---|---:|---:|---:|---:|---:|---:|---:|'])
    for name,proposal in dry['proposals'].items():p.append(f"| {name} | {proposal['table_pairs']} | {proposal['source_columns']} | {proposal['task_variants']} | {proposal['condition_count']} | {proposal['repetitions']} | {proposal['local_a_runs']} | {proposal['llm_calls']} |")
    p.extend(['', '최소안은 main4 + 자연 no_match2, 서로 다른6쌍·6원본이다. 확장안은 main12 + 자연4 + 같은 main에서 양성 제거한 통제12(독립 원본16개, 과제 변형28개)다. B/C/D 순서는 과제·조건·반복 인덱스에 따라 BCD/CDB/DBC로 순환한다. 단회 또는 온도0 반복이 독립성과 통계적 속도 우위를 보증하지 않는다.',
        '변환된 전체 test의425과제(통제 포함)에 세 조건·세 LLM을 적용하면3,825회이며, 현재 차단/중복 격리 전의 이론상 슬롯 수다. 현재 공통 기술 범위의160과제 변형만 전부 실행해도1,440회다. 전체 공식 이진 benchmark와 이번 일부 주석 후보 Top-1 표본 평가는 동일하지 않다.',
        '', '## 연결 확인과 실행 시간','',
        '사전 선택: train / 30166286_0_1837439231599898748 / 원본 index0(Prize) / 후보3개(award, knownFor, rdf-schema#label). 정답·유사도·모델 출력 대신 고정 seed 순서와 original B/C/D 예산 통과로 선정했다. 선택 시각은 connection-plan.json, 동결 시각은 frozen.json에 있다. 원본 조건 하나에서 B→C→D 각1회, 최대3회만 허용하고 교체/재시도하지 않았다. 세 결과가 끝난 후에만 train 정답을 읽었다.',
        '실측·실패·시간 가정은 PUBLIC_CONNECTION_REPORT.md에 별도 작성한다. 이 단계의1개 개발 문제를 연구 정확도/효과 결과로 제시하지 않는다. C/D 서버·사용량이 미확인인 경우 토큰 감소나 성공 처리 시간 우위를 계산하지 않는다.',
        '', '## 실행·중단·재개','',
        '새 유료 리소스나 Google Cloud를 쓰지 않는다. 기존 학생 VM·Qwen3:4b·요금 구성과 매일23:00 KST 자동 종료를 유지한다. 토큰/서버 시간과 VM 가동 시간 비용을 구분하며 시간 단가가 확인되지 않으면 금액을 만들지 않는다. 종료 후 디스크/IP 비용은 별도다.',
        '실제 연결 확인은 v1이었다. 발견한 선행 원격 명령 충돌 전파를 막기 위해 serial-safe-v2 실행 제어를 별도 파일/해시로 동결했다. 모델·프롬프트·데이터는 동일하다. v2는 API 오류를 저장한 직후 다음 호출을 멈추며, 테스트 대역으로 검증했으나 실제 재호출 검증은 하지 않았다. 본 실험 전 C/D 성공 경로와 관리 오류 계측을 별도 확인해야 한다.',
        'v2 runner는22:45 KST부터 새 작업을 시작하지 않는다. 호출 전 슬롯을 영구 예약하고, 중단 시 완료 슬롯은 건너뛰며 결과 없는 예약은 원격 실행 불명으로 보존하고 재호출하지 않는다. 기본 실행은 상태 조회만 한다. 다음날 기존 VM과 인증을 확인한 뒤 --resume으로 미예약 작업만 진행한다. API 불명 상태가 있으면 먼저 Azure 로그로 원격 완료를 확인하고 --ack-remote-finished를 명시한다. 이 플래그는 운영자 확인이며 자동 상태 검증이라고 표시하지 않는다. 원본/코드/설정/계획 해시가 달라지면 재개를 거부하며 POST/실패 모델 요청을 자동 재시도하지 않는다.',
        '```powershell',
        'cd "C:\\Users\\hjlee\\OneDrive\\문서\\ChatGPT\\세미나\\schema-matching-prototype"',
        '# 상태만 확인: 모델 호출 없음',
        '.\\.venv\\Scripts\\python.exe scripts\\run_public_experiment_v2.py --plan minimum',
        '# 이번 연결 확인은 이미 완료. 기록 보존, 추가 호출 없이 조회',
        '.\\.venv\\Scripts\\python.exe scripts\\run_public_experiment_v2.py --plan connection',
        '# 이후 사용자가 규모를 확정한 뒤에만 아래 실행/재개 명령 사용',
        '.\\.venv\\Scripts\\python.exe scripts\\run_public_a.py --plan minimum',
        '.\\.venv\\Scripts\\python.exe scripts\\run_public_experiment_v2.py --plan minimum --execute --max-new-calls 9',
        '.\\.venv\\Scripts\\python.exe scripts\\run_public_experiment_v2.py --plan minimum --execute --resume --max-new-calls 9',
        '# API 불명 상태가 있으면 Azure 원격 완료 확인 후에만 --ack-remote-finished 추가',
        '# 예정 작업 종료 후에만 정답을 여는 오프라인 채점',
        '.\\.venv\\Scripts\\python.exe scripts\\score_public_experiment.py --plan minimum',
        '```',
        '전체 실행은 이번 단계에서 시작하지 않았다. 위 명령은 향후 실행용이며 새 --max-new-calls 제한마다 완료/실패/원격 불명 상태가 남는다. 별도의 요청 없이 maximum budget을 자동 확장하지 않는다.',
        '', '## 현재 가능/미해결','',
        '가능: 임의 양측 CSV의 위치 기반 읽기(중복/빈 헤더 유지)·원본 문자열 보존·양쪽 A/B/C/D 요청·누출 감사·한도 검사·동결된 소규모 표본/실행기·모든 실패/재개 기록·최초 추천 채점. 임의 표의 무호출 미리보기는 scripts/preview_table_pair.py --source 원본.csv --target 대상.csv --source-index 0 --output preview.json이다. 정답 없는 임의 표에는 정확도가 없다.',
        '기존 app.py/files.load_schema의 상품·주문6개 표준, examples/evaluation의 합성 정답, smoke의 상품명 연결은 기존 서비스에 남겼다. 새 연구 엔진은 load_schema/합성 정답을 import하지 않는다. 실제 연구는 별도 CLI 어댑터이며 기존 UI가 임의 양측 연구 실험을 지원하는 것처럼 표시하지 않는다.',
        '미해결: 실제 C/D 관리 채널 실패 원인·성공 시 서버 처리/사용량 계측 확인, 큰 후보/긴 범주 때문에 차단된 범위의 공통 분할 정책, 전체/독립 평가·원천 계열 완전 검증·pretraining 오염 여부·한영 혼용·국내 데이터. 필요 변경은 기존 v1 결과를 보존하고 새 버전으로 평가 전에 동결한다. 사용자 검토·다운로드 기능은 기존 서비스에 보존했다.'])
    (ROOT/'EXPERIMENT_PROTOCOL.md').write_text('\n'.join(p)+'\n',encoding='utf-8')
    print('DATASET_AUDIT.md and EXPERIMENT_PROTOCOL.md generated from actual evidence.')

if __name__=='__main__':main()
