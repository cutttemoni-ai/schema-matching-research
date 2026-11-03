"""Publish aggregate provenance/quality only, never actual row values."""
import json,csv,sys,io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import korea_data_v1 as k,gemini_main30 as o
from schema_match.records import now_iso

def write():
    acq=o.read(k.DATA/'acquisition.json');q=k.quality();d=k.build();manifest={k:v for k,v in acq.items() if k!='files'}
    # Filenames/schema labels, counters and SHA digests only; no original records.
    manifest['files']=acq['files'];folder=k.ROOT/'data-manifests';folder.mkdir(exist_ok=True)
    o.atomic(folder/'korea-public-v1.json',manifest)
    lines=['# 국내 공개데이터 확보·품질 감사','',f"감사 기록 UTC {now_iso()}. 원본은 `datasets/korea-v1/raw`에 보존, 원문 응답/페이지는 `pages`, 직렬화 CSV는 `derived`, 앱 부분표는 `examples`. 모두 Git 제외. 공개 Git에는 행 값·연락처·원 요청·원 응답이 없다.",
        '', '|자료|실제 범위|행×열|인코딩|기준일/날짜 범위|SHA256|','|---|---|---|---|---|---|']
    for name,m in acq['sources'].items():
        lines.append(f"|{name}|{m.get('scope',m.get('format'))}|{m['rows']}×{m['columns']}|{m['encoding']}|{q['sources'][name]['reference_date_range'] or m['reference_date']}|{m['sha256']}|")
    lines+=['','## 공식 출처·실제 파일 경로·조건','']
    for name,m in acq['sources'].items():
        lines += [f"- {name}: [요청 출처]({m['source']})"+(f" / [실제 대체 출처]({m['actual_source']})" if m.get('actual_source') else ''),
            f"  - 다운로드 경로 `{m['download_endpoint']}`. 시각은 로컬 원파일 기록 mtime `{m['raw_file_observed_mtime_utc']}` 기준이며 HTTP 서버가 확인한 정확한 시각으로 주장하지 않는다. 원문 응답의 별도 mtime/해시도 로컬에 유지.",
            f"  - 이용조건: {m['license']}"]
    lines += ['', '전국 음식점의 공식 이관 링크는 requests와 정상 브라우저 모두403→error.html이었다. 우회하지 않았다. 서울시 OA-23056 첨부파일 탭에는 파일이 없어 공식 sheet CSV 내려받기 POST를 사용했다. APVPERMYMD contains2025 조건은 다운로드 전 고정했으며 서울/2025 인허가 일부이지 전국 일반음식점표준데이터 확보 완료가 아니다. 원래 음식점 catalog의 EPSG:5174 설명은 별도로 보존했다.',
        '', '상가 ZIP Range 요청에 서버가206 대신200으로 전체349,070,686바이트를 반환했다. 이를 원본 ZIP으로 보존하고16개 지역 CSV(전남·광주 합본 포함) 중 가장 작은 세종15,637행만 분석했다. 다른 지역도 같은 스키마 계열이며 독립 사례로 세지 않았다. 압축 해제 CSV 바이트는 ZIP 원본과 동일하다.',
        '', '시장/주차장은 공식 CSV 버튼이 JSON 페이지를 받아 브라우저에서 CSV로 직렬화하는 구조다. 동일 공식 columList/standard.json 경로에서 시장1페이지, 주차장2페이지(10,000+8,994)를 받고 원 응답을 보존했다. 문자열은 변환 없이 UTF-8 BOM CSV로 저장, 원 JSON null은 별도 마스크로 구분한다. 공식 다운로드 필터/50,000상한이 있어 전국 모든 기관의 역사자료 완전성을 보증하지 않는다.',
        '', '시장/주차장 JSON-LD의 license는 일반 포털 약관 URL만 있고 명명된 개별 이용범위가 없다. 최초 로컬 manifest의 일괄 자유이용 가정은 검증 후 정정했으며 초기 manifest도 남겼다. 원본 재배포/제품 상용 재배포 권한을 확인했다고 쓰지 않는다. 원본은 Git/이미지에 넣지 않는다. [포털 약관](https://www.data.go.kr/ugs/selectPortalPolicyView.do).',
        '', '## 실제 파일 전 열 검사','', '|자료|열|추정 자료형|빈문자열|공백만|결측률|고유값비율|앞0|숫자통계|날짜범위|','|---|---|---|---:|---:|---:|---:|---:|---|---|']
    public_quality={}
    for name,meta in q['sources'].items():
        public_quality[name]={k:v for k,v in meta.items() if k!='column_quality'}
        public_quality[name]['columns']={}
        for n,col in meta['column_quality'].items():
            f=col['profile']['features'];safe={k:v for k,v in col.items() if k not in ('profile','representative_values_LOCAL_ONLY')}
            safe['profile_summary']={key:f.get(key) for key in ('inferred_type','missing_rate','unique_ratio','date_parse_success_rate','date_min','date_max')};public_quality[name]['columns'][n]=safe
            lines.append(f"|{name}|{n}|{col['metadata_type']}/{f['inferred_type']}|{col['literal_empty_cells']}|{col['whitespace_only_cells']}|{f.get('missing_rate',0):.3%}|{f.get('unique_ratio',0):.3%}|{col['leading_zero_cells']}|{'있음' if 'q50' in f else '없음'}|{str(f.get('date_min',''))}~{str(f.get('date_max',''))}|")
    lines+=['', '각 파일 중복 헤더0·완전 중복행0. 빈 열과 모든 전 열 집계는 공개 요약 JSON, 실제 대표값/상위범주는 Git 제외된 `research-artifacts/korea-v1/quality.json`에서 확인한다. 대표값을 사람이 검토했다고 표시하지 않는다.',
        '', '## 판정 기준과 보존','',
        'CSV는 모든 셀을 문자열로 읽으며 숫자/날짜 추정은 별도 복사에서 한다. 원본 공백·빈문자열·NA/null 문자열·한글·코드의 앞자리0은 남긴다. 프로파일은 양끝 공백 제거 후 빈값을 결측으로 취급하며 결측률은 전체행, 고유값/패턴/범주/날짜 성공률은 비결측값을 분모로 한다. 숫자는 모든 비결측값이 선행0 코드가 아닌 엄격 Decimal일 때만 통계를 만들고, 날짜는 유효 ISO 날짜/시간만 인정한다. 예: 음식점 공백으로 패딩한 날짜는 저장값은 그대로지만 분석 프로파일에서는 날짜로 인식될 수 있다. 코드가 숫자로 추정되어도 의미상 수량으로 변환하지 않는다.',
        '', '전화번호·홈페이지·불필요한 사업체/건물 관리 ID는 원본 보존, 모델/앱 부분표에서는 제외한다. 모델에 원시 행 전체를 보내지 않는다. 허용 열의 전체 프로파일 상위범주에는 실제 문자열이 들어가므로 원 요청/응답·상세 검토표는 공개 Git에 넣지 않는다.',
        '', '주소는 지번/도로명을 구분한다. 상권업종은 상권업종분류/표준산업분류10차와 음식점 인허가 업태가 같은 코드 체계라고 가정하지 않는다. 시장은 개별 상점이 아닌 시설 집합이며 주차장과도 다른 개체다. 주차요금 원·시간 분·시각 HH:MM·구획 면·점포 개·개설연도를 구분한다. 주차 기본/추가 요금은 다른 속성이다. 단위 설명은 공식 명칭/일반 표준 의미를 바탕으로 작성한 요약이며 원문 사전 인용이 아니다.',
        '', '상가·시장·주차장의 위도/경도는 실제 값에서 소수 도 범위를 보이지만 EPSG 메타데이터까지 원 파일에서 확정하지 못했다. 음식점 기존 X/Y의 catalog 설명은 EPSG:5174이고 추가 X좌표/Y좌표의 CRS는 미확인이다. 원점을 추측하거나 5174/5179/WGS84를 같은 좌표로 채점하지 않는다. 좌표 변환을 수행하지 않았고 엄격1:1 정답에서 제외했다.',
        '', '## 실험 부분표·분할·제외','',
        '파일 전체 품질검사와 모델용 부분표를 구분한다. 모델은 각 형식별 seed+원래행번호 SHA 순서256행, 연락처 없는6~9열에서 계산 가능한 모든C특징을 받는다. 값 변경·정답에 맞춘 행 선택·이상치 제거 없음. 행 선택 규칙/인덱스/셀 보존 검사가 로컬 data.json에 있다. 자료형·분위수 결과는 부분표 기준이며 전체 파일과 달라질 수 있다.',
        '', '개발 계열=세종 상가+서울 음식점, 최초 평가 계열=전통시장+주차장. 동일 지역별 형식/모든 헤더·행 변형은 같은 계열이다. 공개표준 간 주소·기관 등 공통 속성/실제 위치의 중복은 있을 수 있으므로 완전한 독립 출처라고 주장하지 않는다. T2D/Valentine 원파일과 바이트 동일 해시는0이나, 부분적인 현실 개체 중복/웹 학습 중복까지 보장하지 않는다.',
        '', 'v1 ID 접두사 뒤 공유 열번호가 남는 통제실험 단서를 추가 감사로 발견했다. 시장 주소1건을 이미 전송한 뒤 나머지23건을 미실행으로 차단했다. v1.1은 독립 해시 대상 ID로 수정하고 이미 전송한 원본 열은 제외, 나머지3열×3조건×2엔진18회로 새로 동결했다. 같은 시장 계열의 다른 열이 앞서 사용되었으므로 완전 미접촉 계열 평가라고 쓰지 않는다. 모델의 의미 응답을 보고 규칙/표본을 튜닝하지 않았으며 중단1건은 새 점수에 합치지 않는다. 상세는 KOREA_V1_1_EVALUATION_PLAN.md.',
        '', '정답은 모델의 결과를 보고 만든 레이블이 아닌 정의 기반 자동 작성 잠정 참조다. 사람이 검토한 벤치마크 정답이 아니다. 모호한 분류체계 변환/시장-상점/좌표 변환 관계는 양성 정답에서 제외한다. 미대응은 명시한 후보들의 정의상 같은 속성이 없는 경우만 지정하며 모든 다른 미주석 쌍에 음성을 부여하지 않는다. 각 과제는 잠정 단일답이고 복합/1:N 변환은 평가하지 않는다.']
    o.atomic(k.ROOT/'KOREA_DATASET_AUDIT.md','\n'.join(lines).encode('utf8'))
    o.atomic(folder/'korea-quality-aggregate-v1.json',public_quality)
    truth=o.read(k.OUT/'provisional-truth.json')
    sanitized=[{key:value for key,value in t.items() if 'LOCAL_ONLY' not in key} for t in truth]
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(sanitized[0]));writer.writeheader()
    for t in sanitized:writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,dict) else v for k,v in t.items()})
    o.atomic(k.ROOT/'KOREA_REFERENCE_REVIEW.csv',stream.getvalue().encode('utf-8-sig'))
    review=['# 국내 공개데이터 잠정 정답 검토표','', '자동 작성이며 사람 검토 미완료. 실제 대표값은 개인정보/사업체명 유출 방지를 위해 공개 표에서 제외했으며 로컬 `research-artifacts/korea-v1/provisional-truth.json`과 `quality.json`에서 양쪽 정의/대표값/불확실성을 대조할 수 있다. 이 표의 정답 파일은 모델/제품이 읽지 않는다. v1.1 대상 ID는 별도 독립 해시이며 의미 정답을 바꾼 것이 아니다.',
        '', '|문제|원본열|대상열 또는 없음|판정 근거|','|---|---|---|---|']
    for t in sanitized:review.append(f"|{t['task_id']}|{t['source_name']}|{t['target_name'] or '없음'}|{t['basis']}|")
    o.atomic(k.ROOT/'KOREA_REFERENCE_REVIEW.md','\n'.join(review).encode('utf8'))
    print('Aggregate-only audit, provenance and provisional-review files written; no model calls')
if __name__=='__main__':write()
