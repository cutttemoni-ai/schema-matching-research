# T2D-SM-WH 실제 데이터 감사

감사: 2026-11-02T05:08:24.304982+00:00 (UTC). 다운로드: 2026-11-02T05:04:45.517074+00:00 (UTC).

## 출처·파일·이용 조건

공식 출처: https://webdatacommons.org/structureddata/smb/ . 공식 페이지 HTML의 실제 링크를 파싱해 내려받았으며 주소를 추측하지 않았다. GitHub 링크의 HTTP 리디렉션은 acquisition.json에 보존했다. 실제 다운로드는 모두 HTTP200이었다. 웹 읽기 도구는 ZIP을 텍스트로 표시하지 못했지만 Python 다운로드는 성공했으며 대체/합성 데이터로 대체하지 않았다.

| 파일 | 실제 바이트 | SHA-256 |
|---|---:|---|
| t2d_sm_wh.zip | 1591174 | `e3c5f4c4313ac7c000f9c6531383a6d21e56658378c2698f5ff757688feda7e7` |
| t2d_sm_supplement_metadata.zip | 215139 | `6339bdb5791b1b0869c24b6f93ea54d6ff1717f57911e55da370178cc631cb3e` |

ZIP 원본과 압축 해제 파일은 datasets/wdc_smb/raw/에 보존한다. 원본을 덮어쓰거나 CSV 헤더·값을 수정하지 않았다. 각 파일의 경로·크기·SHA-256 전체 목록은 datasets/wdc_smb/acquisition.json에 있다. 원문 HTML도 보존했다.
공식 저장소 LICENSE(https://github.com/wbsg-uni-mannheim/wdc-smb/blob/main/LICENSE)는 BSD-3-Clause이며 저작권/조건/면책 보존 및 기여자 명의의 무단 보증 금지 조건을 담고 있다. 사본은 raw/repository-LICENSE.txt에 저장했다. 아카이브별 별도 라이선스 문서와 원천 Web 페이지·DBpedia 데이터의 개별 권리 범위는 이 감사에서 확정하지 못했다. 저장소 라이선스를 모든 원천 콘텐츠의 권리 해소나 무제한 상업적 재배포 보장으로 확대하지 않는다. 제출 자료에는 출처·저작권 고지를 유지하고 원본 전체 재배포 여부는 별도 확인한다.

## 실제 구조

```text
datasets/wdc_smb/raw/
  t2d_sm_wh.zip
  t2d_sm_wh/
    train/{webtables/(71 CSV), dbpedia_tables/(71 CSV), train_correspondences.csv}
    valid/{webtables/(18 CSV), dbpedia_tables/(18 CSV), valid_correspondences.csv}
    test/{webtables/(89 CSV), dbpedia_tables/(89 CSV), test_correspondences.csv}
    .ipynb_checkpoints/ 및 split 내부 checkpoint 디렉터리: 실행 입력에서 제외
  t2d_sm_supplement_metadata.zip
  t2d_sm_supplement_metadata/(178 JSON, 하위 경로는 acquisition inventory 참조)
  official-page.html / repository-LICENSE.txt
```

아래 수치는 실제 CSV를 csv.reader로 읽어 집계했다. 공식 웹 페이지 수치를 복사해 집계한 것이 아니다.

| 공식 분할 | 표 쌍 | 원본/대상 열 | 주석 원본 열 | 양성 | 음성 | 정답 행 | 전체 열 조합 | 미주석 조합 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| train | 71 | 383 / 359 | 351 | 177 | 878 | 1055 | 2031 | 976 |
| valid | 18 | 87 / 101 | 85 | 59 | 263 | 322 | 515 | 193 |
| test | 89 | 453 / 468 | 413 | 209 | 1056 | 1265 | 2448 | 1183 |

합계178쌍·356표·원본923열/대상928열(총1,851열), 정답2,642행(양성445/음성2,197), 전체 가능한 열 조합4,994개 중 미주석2,352개다.

## 정답 스키마·식별자·주석 범위

`[빈 열 이름], table_name, column_name_left, column_index_left, column_name_right, column_index_right, label`. 첫 빈 열은 정답 CSV의 내보내기 행 번호이며 표의 열이 아니다. table_name에 .csv를 붙인 동일 파일명이 webtables(원본)와 dbpedia_tables(대상)를 연결한다.
인덱스는 0부터 시작한다. 실제 파일 헤더와 양쪽 인덱스의 이름을 대조한 5,284회 검사가 전부 일치했으며 1-based 해석은 일치0이었다. label=1은 해당 열 쌍의 양성, label=0은 그 열 쌍의 음성이다. label=0 또는 양성 부재가 원본 열 전체의 no_match를 의미하지 않는다.
주석은 전체 Cartesian 후보를 완전 판정하지 않는다. 원본 열마다 모든 대상 열의 주석이 있는 행은 train46/valid23/test55개뿐이다. 미주석 쌍은 unknown으로 유지하고 후보에서 제외한다. GT의 이름 필드는 감사에만 사용하며 모델의 메타데이터는 실제 CSV 헤더에서 읽는다.

## 품질 점검

| 분할 | 빈 헤더 | 중복 헤더 위치 | 빈 열 | 결측 셀/전체 셀 | 동일 정답 중복 | 충돌 정답 키 |
|---|---:|---:|---:|---:|---:|---:|
| train | 0 | 0 | 6 | 20383 / 119281 | 0 | 0 |
| valid | 0 | 0 | 0 | 3909 / 22699 | 0 | 0 |
| test | 0 | 0 | 10 | 18360 / 152246 | 0 | 0 |

결측은 공백 제거 후 빈 문자열이다. 실제 합계42,652/294,226셀, 빈 열16개이며 NA/null/None/NaN/N/A 표기119개는 원문 문자열로 보존하고 결측으로 임의 변환하지 않았다. 실제 표에서 빈/중복 헤더는0, 파일 파싱 오류0, 인덱스·이름 불일치0이다. 어댑터는 향후 빈/중복 헤더가 있어도 위치로 구분하며 원본 값은 문자열 그대로 보존한다.
동일 열 쌍의 중복 주석과 양/음 충돌은0이나, train에서 두 원본 열이 같은 대상에 양성으로 연결되는 원본 열2개가 있었다. 공식 1:1 가정과 맞지 않아 해당2열을 제외했다. multiple positive/invalid/no annotations 등 제외 내역은 exclusions.jsonl에 별도 저장했다. 파일명·열 위치·제외 사유를 확인할 수 있다.

| 분할 | 주 Top-1 문제 | 자연 발생 no_match | 통제 no_match | 제외 사유별 원본 열 수 |
|---|---:|---:|---:|---|
| train | 175 | 6 | 175 | no_positive_in_incomplete_annotations_not_no_match: 168; no_annotations: 32; multiple_sources_positive_same_target: 2 |
| valid | 59 | 6 | 59 | no_positive_in_incomplete_annotations_not_no_match: 20; no_annotations: 2 |
| test | 209 | 7 | 209 | no_positive_in_incomplete_annotations_not_no_match: 197; no_annotations: 40 |

주 문제443개, 자연 no_match19개(모든 대상의 명시적 음성 확인), 통제 no_match443개(알려진 양성 제거·명시적 음성만 유지)다. 통제 문제는 같은 원본의 변형이며 독립 원본 열 수에 더하지 않는다. 불완전 주석에서 양성 없는385열과 주석 전혀 없는74열을 no_match 정답으로 만들지 않았다.

## 설명과 분할·계열 중복

보조 JSON178개가 모든 표 쌍을 연결한다. 실제 키는 다음과 같다: TableContextTimeStampAfterTable, TableContextTimeStampBeforeTable, hasHeader, hasKeyColumn, headerPosition, headerRowIndex, keyColumnIndex, lastModified, pageTitle, recordEndOffset, recordOffset, s3Link, tableNum, tableOrientation, tableType, textAfterTable, textBeforeTable, title, url.
이는 페이지 URL·제목·주변 텍스트·시각·구조 메타데이터이며 구조화된 열별 설명은 제공되지 않는다. 이번 B/C/D의 설명은 양쪽 모두 빈 문자열이다. 주변 페이지 문맥은 제외하며 GT로 설명을 생성하지 않는다. 따라서 설명 제거에 따른 성능 하락은 이 데이터/설정으로 측정할 수 없다.
분할 사이 동일성/같은 페이지 연결 그룹은 실제8개다(기준별: {'source_page': 5, 'sha256': 2, 'unordered_body_hash': 1}). 중복 기준들은 중첩될 수 있으므로 그룹 수를 독립 표 수처럼 합산하지 않는다. 파일명만 다른 동일 바이트, 행 순서를 무시한 동일 값 배열, 동일 source URL(쿼리/fragment 제외)을 함께 검사했다.
이 연결 성분이 train/valid와 겹치는 test 표 쌍은 7개다. 공식 분할을 이동시키지 않고 test 후보에서 격리한다. 표본 내부에서도 동일 연결 성분은 한 번만 선택한다. 동일 DBpedia 헤더 템플릿의 교차 분할 그룹도 1개였으나 이는 다른 행의 같은 스키마일 수 있어 동일 데이터라고 단정하지 않는다.
웹 도메인/토픽은 분할 사이 공유될 수 있다. 행이 부분적으로 겹치는 모든 근접 복제, 원래 DBpedia 질의/클래스·생성 계열의 완전 분리까지 증명하지 못했다. 현재 필터는 식별 가능한 동일 표/원본 페이지 수준의 보수적 격리이며 도메인 외 일반화나 완전 독립 계열 평가라고 주장하지 않는다. 자세한 그룹은 dataset-audit.json의 duplicate_or_family_groups 및 cross_split_dbpedia_header_templates에 있다.

## 재현

획득: scripts/acquire_wdc.py. 원본 감사: scripts/audit_wdc.py. 전체 로컬 점검: scripts/dry_run_wdc.py. 동결 후에는 dry-run이 기존 산출물을 덮어쓰지 않는다. 실행/재개 시 원본 inventory의 모든 해시를 검사한다. 독립 연구 성능 평가 결과는 아직 없다.
