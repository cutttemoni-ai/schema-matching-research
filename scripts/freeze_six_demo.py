"""Create the six synthetic DEVELOPMENT cases once, before any model call."""
import csv
import io
import json
import sys
from hashlib import sha256
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.baseline import normalize_name
from schema_match.config import ROOT,Settings
from schema_match.records import json_bytes,now_iso

CASES=[
    ('S01','명확한 메타데이터','product_name','판매 상품의 이름','string',
     ['무선 마우스','유선 키보드','USB 허브','노트북 거치대','무선 마우스','USB 허브'],
     'unique','product_name','이름과 설명이 상품명을 명시한다.','명확한 개발 사례이며 다국어 일반화의 증거가 아니다.'),
    ('S02','명확한 메타데이터','주문수량','이 주문에 포함된 상품 개수','integer',
     ['1','2','3','1','5','2'],
     'unique','quantity','설명이 주문 상품 개수를 명시한다.','A는 한글을 보존하지만 번역·한영 별칭은 사용하지 않는다.'),
    ('S03','부족한 메타데이터·프로파일 단서','COL_A','','unknown',
     ['무선 마우스','유선 키보드','USB 허브','노트북 거치대','무선 마우스','USB 허브'],
     'unique','product_name','C의 상위 범주 문자열은 상품명 의미를 드러낸다.','D는 문자열 범주 값을 제외한다. 형태 통계만으로 상품명 의미를 확정할 수 없으며 B/D의 검토 요청도 실무상 합리적이다. Top-1에서는 검토를 정답으로 세지 않는다.'),
    ('S04','부족한 메타데이터·프로파일 단서','COL_B','주문 접수 이력의 기록 시점. 날짜 형식 정보 없음','unknown',
     ['2026-10-25','2026-10-28','2026-11-01','2026-11-02','2026-11-04',''],
     'unique','order_date','부분적인 업무 설명과 엄격한 ISO 날짜 파싱 결과가 주문일 후보를 지지한다.','설명만으로 B도 맞힐 수 있다. 날짜 분포만으로 모든 날짜가 주문일이라고 증명할 수 없다.'),
    ('S05','표준 후보 미대응','배송요청메모','고객이 남긴 배송 요청 문장','string',
     ['문 앞에 놓아주세요','도착 전 전화','경비실 보관','','파손 주의','문 앞에 놓아주세요'],
     'unmatched',None,'후보에는 배송 요청·자유 메모가 없다.','상품명 등 문자열 후보에 연결하면 오연결이다. 검토는 no_match의 정답으로 세지 않는다.'),
    ('S06','제공 정보로 구분 불가능','AMT','금액','number',
     ['12000','18000','24000','30000','12000',''],
     'ambiguous',None,'단가와 총액은 같은 값·분포를 가질 수 있다. 주변 열 관계와 추가 설명이 없다.','숨겨진 생성 의도를 정답으로 두지 않는다. 단가·총액 중 어느 하나를 확정하면 근거 부족이다.'),
]

def main():
    dest=ROOT/'demo_cases'/'six_v1'
    if (dest/'frozen.json').exists():raise SystemExit('이미 고정됨. 덮어쓰기·재튜닝 금지.')
    dest.mkdir(parents=True,exist_ok=True)
    (dest/'inputs').mkdir(exist_ok=True)
    metadata=[];annotations=[]
    for identifier,category,name,description,dtype,values,kind,target,basis,limit in CASES:
        buffer=io.StringIO(newline='');writer=csv.writer(buffer);writer.writerow([name]);writer.writerows([[v] for v in values])
        relative=f'demo_cases/six_v1/inputs/{identifier}.csv'
        (ROOT/relative).write_bytes(buffer.getvalue().encode('utf-8-sig'))
        order=[['B','C','D'],['C','D','B'],['D','B','C']][(int(identifier[1:])-1)%3]
        metadata.append({'case_id':identifier,'input_path':relative,'source':{'id':'src_001','name':name,'description':description,'data_type':dtype},'method_order':order})
        annotations.append({'case_id':identifier,'category':category,'kind':kind,'expected_target':target,'basis':basis,'limit':limit,
            'acceptable_review_targets':[None,'unit_price','total_amount'] if kind=='ambiguous' else []})
    (dest/'metadata.json').write_bytes(json_bytes({'version':'six-development-v1','synthetic':True,'family':'six_synthetic_demo_v1','cases':metadata}))
    truth=ROOT/'evaluation'/'six_v1_annotations.json';truth.write_bytes(json_bytes({'version':'six-development-v1','cases':annotations}))
    doc=['# 6열 소규모 개발 검증 — 호출 전 고정 계획','',f'고정 시각(UTC): {now_iso()}','',
        '직접 만든 시연용 합성 데이터이며 기존 예제와 모두 개발용이다. 독립 연구 평가 데이터가 아니다. 여섯 파일은 같은 생성 계열이고 독립 표본 수를 주장하지 않는다.',
        '', '## 고정 후보와 정보 경계','',
        '모든 사례에 schemas/product_order.json의 동일 후보 6개를 제공한다. product_code: 앞자리 0을 보존하는 상품 식별 코드(string), product_name: 상품 이름(string), quantity: 주문 상품 개수(integer), unit_price: 한 개 판매 단가(number), total_amount: 주문 행 합계(number), order_date: 주문 접수 날짜(date).',
        '원본 ID는 각 독립 파일에서 src_001이다. A는 이름만, B는 이름·설명·자료형만, C는 B+계산 가능한 전체 프로파일, D는 B+C의 같은 계산 결과에서 고정 규칙으로 선택한 일부 특징을 받는다. 주변 열은 없다. 정답·판정 설명은 evaluation/에 분리하고 모든 호출이 끝난 뒤에만 평가 코드가 읽는다.',
        'C의 top_categories에는 실제 값 문자열이 있다. 작은 파일에서는 모든 비결측 범주가 노출될 수 있다. D 문자열 규칙에는 실제 범주 값이 없다. 따라서 C/D 차이는 특징 수와 실제 값의 의미 정보 포함 여부를 함께 반영하며 선택 규칙 효과만 분리하지 못한다.',
        '', '## 호출 전 사례 정의','']
    for m,a in zip(metadata,annotations):
        doc.extend([f"### {m['case_id']} — {a['category']}",'',
            f"입력: `{m['source']['name']}`, 설명 `{m['source']['description'] or '(없음)'}`, 자료형 `{m['source']['data_type']}`. 원본: `{m['input_path']}`. 값과 모든 특징은 해당 고정 CSV에서 계산한다.",
            f"판정: {a['kind']}; "+('고유 대상 없음. needs_review 요청 여부 별도 평가. null 또는 unit_price/total_amount 잠정 대상이면 허용 가능한 검토 판단.' if a['kind']=='ambiguous' else f"기준 대상 `{a['expected_target']}`; "+('no_match/null이 정답.' if a['kind']=='unmatched' else 'matched 및 해당 ID일 때 Top-1 정답.')),
            f"구분 근거: {a['basis']}",f"한계: {a['limit']}",f"실행 순서: A(로컬) → {' → '.join(m['method_order'])}.",''])
    doc.extend(['## 실행·채점 규약','',
        'A 로컬 6건, B/C/D 각 열 1회씩 최대 18회. 자동 재시도 0. 호출 슬롯을 디스크에 선점하고 같은 프로토콜 재실행을 차단한다. 실패도 보존한다. 입력/응답 한도 초과는 실패이며 특징이나 응답을 몰래 자르지 않는다. 기존 1~3열 UI 한도를 유지하고 한 열씩 실행한다.',
        'B/C/D 순서를 BCD/CDB/DBC로 순환해 각 방법이 각 순번에 두 번 오게 한다. 단회·동일 계열이므로 속도의 통계적 우위를 입증하지 않는다. 기존 모델·프롬프트·후보·출력 형식·온도·컨텍스트·출력 상한·D 규칙·A 임계값을 유지한다. 모델링 코드와 설정은 frozen.json 해시로 확인한다. 결과에 맞춘 값·규칙·프롬프트 변경을 하지 않는다.',
        '주 지표: 고유 대상 ID가 있는 S01~S04의 정답 수 / 4 및 Top-1. needs_review와 실패는 분모에 남고 정답이 아니다. S05는 no_match 정답과 미대응 오연결 여부(잠정 non-null도 포함)를 따로 표시한다. 부가 지표로 S01~S05의 확정 가능한 판정 정답 수 / 5를 표시할 수 있다. S06은 Top-1에서 제외하고 검토 요청 여부 및 허용 검토 대상 여부를 별도 표시한다. S06의 matched는 근거 없는 확정 연결이며 no_match는 불확실성과 미대응을 혼동한 것이다.',
        '원 모델과 공통 정책 후 최초 추천을 모두 보존·채점한다. 사용자의 수정 결과는 모델 정확도에 쓰지 않는다. 모든 6열 기준 검토 비율·실패·호출·실측 토큰·시간을 함께 표시한다. A 토큰 0은 LLM 미사용을 뜻하며 API 보고값이 아니다. API 미제공 사용량은 미제공으로 둔다. C/D 토큰 감소율은 실제 제공된 토큰 합계로 계산하고 VM 요금 절감률로 표현하지 않는다.',
        '시간은 파일 파싱, 공유 프로파일/준비, 각 방법 독립 환산(프로파일+선택+매칭), API 왕복 및 서버 타이머를 분리한다. CSV 선택·브라우저 렌더링은 서버 측 전체 시간에 포함하지 않는다. C/D에 같은 프로파일 비용을 각각 배분한 값은 실제로 두 번 계산한 시간이 아니다.',
        '도움 사례 선택: S03/S04 중 B가 틀리거나 검토/실패하고 C 또는 D가 올바르게 matched인 첫 사례. 없으면 도움 확인 없음으로 보고한다. 실패/검토 시연은 S06을 우선 사용한다. 단회 결과가 나쁘더라도 재튜닝·재호출하지 않는다.',
        '', '## 고정 버전','',
        f"A name-similarity-v0; 실제 확인: normalize_name(' 주문_수량-Ａ ') = {normalize_name(' 주문_수량-Ａ ')}. 한글 보존. 정규화 버그 수정 없음. 한영 번역·별칭은 미구현.",
        'B/C/D BCD-v4-common, Qwen3:4b, compact_v1(한 열 출력160), context8192, temperature0, think=false, keep_alive=-1. D 자료형 기반 선택 프로파일 v0, A 임계값0.60. VM·모델·요금·한국시간23시 자동 종료 유지.'])
    (ROOT/'SIX_CASE_PLAN.md').write_text('\n\n'.join(doc)+'\n',encoding='utf-8')
    code=['baseline.py','comparison.py','matching.py','profiles.py','review.py','limits.py','output_schema.py','ollama_provider.py','azure_vm_provider.py','azure_run_command.py']
    paths=[str(p.relative_to(ROOT)).replace('\\','/') for p in (dest/'inputs').glob('*.csv')]+['demo_cases/six_v1/metadata.json','evaluation/six_v1_annotations.json','SIX_CASE_PLAN.md','schemas/product_order.json','config/comparison_v0.json']+[f'schema_match/{p}' for p in code]
    frozen={'version':'six-development-v1','frozen_at':now_iso(),'max_calls':18,'automatic_retries':0,'settings':Settings.from_env().__dict__,
        'normalization_probe':normalize_name(' 주문_수량-Ａ '),'sha256':{p:sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}}
    with (dest/'frozen.json').open('xb') as handle:handle.write(json_bytes(frozen))
    print(json.dumps({'frozen_at':frozen['frozen_at'],'cases':6,'max_calls':18,'normalization':frozen['normalization_probe']},ensure_ascii=False))

if __name__=='__main__':main()
