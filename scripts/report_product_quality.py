"""Post-evaluation descriptive report/default selection by pre-frozen criterion. No inference."""
import sys,json
from pathlib import Path
from collections import Counter
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import product_campaign_v1 as c
from schema_match import product_data_v1 as d
from schema_match import gemini_main30 as s
from schema_match.product_score_v1 import csvbytes
from schema_match.records import now_iso

def paired(rows,left,right):
    lookup={(r['task_id'],r['condition'],r['method']):r for r in rows};pairs=[]
    keys=sorted({(r['task_id'],r['condition']) for r in rows})
    for task,condition in keys:
        l=lookup.get((task,condition,left));r=lookup.get((task,condition,right))
        if not l or not r:continue
        both=l.get('input_tokens') is not None and r.get('input_tokens') is not None and l.get('cost_usd') is not None and r.get('cost_usd') is not None
        pairs.append({'task_id':task,'condition':condition,'left':left,'right':right,'source':l['source_name_original'],'kind':l['kind'],
            'left_correct':l['correct'],'right_correct':r['correct'],'left_category':l['category'],'right_category':r['category'],
            'left_target':l.get('target_name'),'right_target':r.get('target_name'),'expected':l.get('expected_name'),
            'left_reason':l['reason'],'right_reason':r['reason'],'paired_usage':both,
            'left_input':l.get('input_tokens'),'right_input':r.get('input_tokens'),'left_cost':l.get('cost_usd'),'right_cost':r.get('cost_usd')})
    complete=[v for v in pairs if v['paired_usage']];a=sum(v['left_input'] for v in complete);b=sum(v['right_input'] for v in complete)
    fa=sum(v['left_cost'] for v in complete);fb=sum(v['right_cost'] for v in complete)
    return {'left':left,'right':right,'planned':len(pairs),'improved':sum(not v['left_correct'] and v['right_correct'] for v in pairs),
        'worsened':sum(v['left_correct'] and not v['right_correct'] for v in pairs),
        'semantic_to_correct':sum(v['left_category']=='semantic_error' and v['right_correct'] for v in pairs),
        'review_to_correct':sum(v['left_category']=='needs_review' and v['right_correct'] for v in pairs),
        'correct_to_semantic':sum(v['left_correct'] and v['right_category']=='semantic_error' for v in pairs),
        'correct_to_review':sum(v['left_correct'] and v['right_category']=='needs_review' for v in pairs),
        'paired_usage_n':len(complete),'missing_pairs':len(pairs)-len(complete),'left_input':a,'right_input':b,'input_reduction':(a-b)/a if a else None,
        'left_cost':fa,'right_cost':fb,'cost_reduction':(fa-fb)/fa if fa else None,
        'paired_left_correct':sum(v['left_correct'] for v in complete),'paired_right_correct':sum(v['right_correct'] for v in complete)},pairs

def main():
    p=s.read(c.OUT/'evaluation-plan.json');c.verify(p)
    if any(c.read_result(j) is None or c.read_result(j)['execution_category']=='uncertain' for j in p['jobs']):raise ValueError('Final evaluation not terminal; do not select product default')
    dev=s.read(c.OUT/'development-results.json');final=s.read(c.OUT/'evaluation-results.json');freeze=s.read(c.OUT/'D1-freeze.json');registry=s.read(c.OUT/'tasks.json');features=d.load_features()
    assert s.filehash(c.ROOT/'schema_match/product_score_v1.py')==s.read(c.OUT/'score-definition-seal.json')['sha256']
    totals={g['method']:g for g in final['totals']};C=totals['C'];D1=totals['D1'];comparison,details=paired(final['rows'],'C','D1')
    qualify=D1['top1']>=C['top1'] and D1['auto_link_precision_lower_bound'] is not None and C['auto_link_precision_lower_bound'] is not None and D1['auto_link_precision_lower_bound']>=C['auto_link_precision_lower_bound'] and D1['auto_link_coverage']>=C['auto_link_coverage'] and comparison['right_cost']<=comparison['left_cost'] and comparison['paired_usage_n']>0
    default='D1' if qualify else 'C'
    decision={'version':'product-default-v1','status':'evaluated_candidate','decided_at':now_iso(),'default_method':default,'D1_active_variant':freeze['active_variant'],
        'criterion':p['product_selection_rule'],'criterion_satisfied':qualify,'C_metrics':C,'D1_metrics':D1,'paired_cost':comparison,
        'mandatory_user_confirmation':True,'commercial_accuracy_certified':False,'model':p['config']['model'],'evaluation_plan_hash':s.filehash(c.OUT/'evaluation-plan.json'),
        'scope':'T2D annotated candidate sets +3 fabricated original-lineage pairs; product standard6 all-candidate accuracy not independently established'}
    path=c.ROOT/'config/product_default_v1.json'
    if path.exists():
        prior=s.read(path)
        if prior['default_method']!=default or prior['evaluation_plan_hash']!=decision['evaluation_plan_hash']:raise ValueError('Product default already decided; no silent post-result tuning')
        decision=prior
    else:s.atomic(path,decision,True)
    comparisons=[];allpairs=[]
    for left,right in (('B','C'),('D0','D1'),('C','D1')):
        g,rows=paired(final['rows'],left,right);comparisons.append(g);allpairs+=rows
    devcomparisons=[]
    for left,right in (('C','C_no_categories'),('D0','D0_representatives'),('D0_representatives','D1')):
        g,_=paired(dev['rows'],left,right);devcomparisons.append(g)
    source_features=[features['columns'][t['source_column_id']]['full_profile']['features'] for t in p['tasks']]
    source_types=dict(Counter(v['inferred_type'] for v in source_features));stats={'numeric_aggregates':sum('numeric_min' in v for v in source_features),
        'date_ranges':sum('date_min' in v for v in source_features),'source_types':source_types,
        'four_digit_year_shape_dominant_sources':sum(features['extensions'][t['source_column_id']]['extra']['parse_evidence']['four_digit_1000_2999_count']>=.9*max(1,features['columns'][t['source_column_id']]['full_profile']['features']['non_missing_count']) for t in p['tasks']),
        'numeric_positive_source_names':[features['columns'][t['source_column_id']]['name'] for t in p['tasks'] if t['kind']=='main' and features['columns'][t['source_column_id']]['full_profile']['features']['inferred_type'] in ('integer','number')]}
    latencies=[]
    for m in p['methods']:
        import statistics
        values=[r['model_call_seconds'] for r in final['rows'] if r['method']==m and r.get('model_call_seconds') is not None]
        latencies.append({'method':m,'observed':len(values),'missing':90-len(values),'sum_seconds':sum(values),
            'mean_seconds':statistics.mean(values) if values else None,'median_seconds':statistics.median(values) if values else None,'maximum_seconds':max(values,default=None)})
    failed=[{k:r.get(k) for k in ('id','method','condition','category','http_status','error','task_id')} for r in final['rows'] if r['method']!='A' and r['category'] not in ('correct','semantic_error','needs_review','unjudged')]
    result={'at':now_iso(),'development':dev,'final':final,'decision':decision,'paired_comparisons':comparisons,'development_contrasts':devcomparisons,
        'profile_coverage':stats,'latency':latencies,'failures':failed,'global_progress':c.global_status(),'new_inferences_by_reporting':0,'past_results_merged':False}
    s.atomic(c.ROOT/'PRODUCT_QUALITY_COMPARISON.json',result);s.atomic(c.ROOT/'PRODUCT_QUALITY_COMPARISON.csv',csvbytes(final['rows']));s.atomic(c.ROOT/'PRODUCT_QUALITY_PAIRS.csv',csvbytes(allpairs))
    lines=['# 제품 후보 품질 보고서','',f"보고 UTC {result['at']}. 기본 방법은 **{default}**로 선택했다. 후보 D v1은 개발 뒤고정한 `{freeze['active_variant']}`다. 기준은 최종호출 전계획의 `{p['product_selection_rule']}`이며 결과를보고선택기준·규칙·프롬프트를바꾸지않았다. 이는 시제품 기본값 선택이며 동등성/유의성/상용인증이 아니다.",
        '', '## 데이터 확보·보존·독립성 범위','', 'Valentine 공식602MB ZIP에서목록/크기확인후부분HTTP로28파일(약9.54MB해제)을확보했다. 개별SHA256·ZIP CRC·출처·날짜·CC BY4.0 레코드·원자료조건미확인범위는 PRODUCT_DATASET_AUDIT.md와acquisition.json에있다. 코드라이선스를데이터권리로대체하지않았다. 변형/생성벤치마크이며 실제거래처데이터가 아니다. GDC는원자료미포함/재구성필요로미평가다.',
        '가족분할은개발시작전에동결했다. 개발T2D5+Magellan1, 최종T2D27+OpenData/TPCDI/ChEMBL3계열. 기존270의30성분·과거개발/평가/알려진중복제외를유지했다. 바이트/행순서독립전체본문중복검사에서외부와T2D간일치0. 단순스키마유사성은같은데이터라고하지않았고원페이지/더넓은생성계열/사전학습중복의완전한배제는미확인이다.',
        '최종30원본은양성28+생성계보미대응2다. 자연미대응0으로자연미대응오연결률은미평가이지0%가아니다. T2D는명시양성·음성의주석후보내Top1, 외부3쌍은공유PK/비공통원래열계보를검증한범위다. Wikidata는불일치edge/정답완전성미확인으로제외했고초기분할과사전예약성분승격기록을보존했다. 미주석쌍을자동음성으로하지않았고복합/복수정답을단일대상으로강제하지않았다. 같은원본3변형을독립원본으로세지않는다.',
        '기존270의점수·원응답·A~D v0 코드와설정은past-preservation.json으로그대로보존한다. 이번연구결과와합산하거나과거대비상승을D1수정효과로주장하지않는다.',
        '', '## D v1 동결과 개발 대조','', '후보는2개만검토했다. ①D0+대표값(최빈1/seed기준고유값1/선택값들과문자유사도차이가큰값1, 최대3개, 각80자이하의전체문자열·빈도·선택이유), ②같은대표값에부분숫자/ISO날짜파싱·단위·코드/연도형식·직렬화특징예산을더한후보. 긴값을잘라쓰지않고대표값선택에서제외한수/빈도를기록하며다른통계의행이나분모는제거하지않는다. 원본/대상동일함수, 원시행배열전송0. 정확한규칙·seed·예산·근거는config/product_d1_v1.json 및D1-freeze.json에있다.',
        '실제선택은D0+대표값후보다. 확장파싱후보는동률정답에입력이더커선택되지않았다. 그러므로최종D1이부분날짜·단위기준까지개선했다고주장하지않는다. 선택되지않은파서는원시값보존·선행0·단위혼합·부분날짜·분모검사를통과했지만개발모델표본은문자열6원본이었다.',
        '', '| 개발 방법 | 정답/예정 | 자동연결후보 정답/후보 | 후보비율 | 검토비율 | 입력(관측/누락) |', '|---|---:|---:|---:|---:|---|']
    for g in dev['totals']:
        lines.append(f"|{g['method']}|{g['correct']}/{g['planned']}|{g['correct_auto_links']}/{g['auto_links']}|{g['auto_link_coverage']:.1%}|{g['model_needs_review_ratio']:.1%}|{g['input_tokens']}|")
    lines+=['', 'C_no_categoriesは値文字列のみ除去し頻度/比率を保持する条件で、その他の設定は同じ。'.replace('C_no_categoriesは値文字列のみ除去し頻度/比率を保持する条件で、その他の設定は同じ。','C_no_categories는범주값문자열만제거하고빈도/비율및다른조건을유지했다. D0_representatives는대표값·빈도·역할묶음을추가했으므로그대조만으로빈도와문자열자체의효과를분리하지는못한다. 동일토큰예산무작위대조는60회예산안에추가하지않았다. 단회관측/6문자열계열이므로원인이나일반효과를확정하지않는다. Magellan개발양성참조외에는unjudged로다루며전체미주석쌍을음성으로하지않았다.'),
        '', '## 별도 최종 평가','', '| 조건 | 방법 | 정답/예정 | Top1 | 자동연결후보 정답/후보 | 후보비율 | 검토비율 | 상태건수 |', '|---|---|---:|---:|---:|---:|---:|---|']
    for g in final['groups']:
        lines.append(f"|{g['condition']}|{g['method']}|{g['correct']}/{g['planned']}|{g['top1']:.1%}|{g['correct_auto_links']}/{g['auto_links']}|{g['auto_link_coverage']:.1%}|{g['model_needs_review_ratio']:.1%}|{g['categories']}|")
    lines+=['','matchedかつID/状態/JSON検証通過を自動リンク候補と定義する。'.replace('matchedかつID/状態/JSON検証通過を自動リンク候補と定義する。','자동확정지표는사용자수정전 matched 및ID/상태/JSON검증을통과한연결을자동연결후보로보는시뮬레이션이다. 실제앱은사용자확정·충돌해결전내보내지않는다. no_match와needs_review는검토대상이다. 전체를검토로돌려고정확도라고하지않으며후보분모와전체처리비율을함께표시한다. 모델자체의신뢰도숫자를확률로쓰지않았다.'),
        '', '## 자료형·미대응','',f"실제원본프로파일범위 `{stats}`. 숫자양성의이름은위에공개했으며연도나코드에편중되면다양한수량/가격의숫자업무를평가했다고하지않는다. 날짜범위가없는원본은날짜매칭효과미평가다.",
        '', '| 방법 | 양성정답/예정 | 생성미대응정답/예정 | 생성미대응 잘못된자동연결/예정 | 자연미대응 |', '|---|---:|---:|---:|---|']
    for g in final['totals']:lines.append(f"|{g['method']}|{g['main']['correct']}/{g['main']['planned']}|{g['generated_none']['correct']}/{g['generated_none']['planned']}|{g['generated_none']['wrong_auto_links']}/{g['generated_none']['planned']}|미평가(0원본)|")
    lines+=['','## 동일 문제의 품질·토큰·비용 전환','']
    for g in comparisons:
        tr='미산정' if g['input_reduction'] is None else f"{g['input_reduction']:.1%}";fr='미산정' if g['cost_reduction'] is None else f"{g['cost_reduction']:.1%}"
        lines.append(f"- {g['left']}→{g['right']}: 정답전환+{g['improved']}/−{g['worsened']}; 의미오답→정답{g['semantic_to_correct']}, 검토→정답{g['review_to_correct']}, 정답→의미오답{g['correct_to_semantic']}, 정답→검토{g['correct_to_review']}. 사용량비교{g['paired_usage_n']}/{g['planned']}쌍, 누락{g['missing_pairs']}; 입력{g['left_input']}→{g['right_input']}({tr}감소), 비용${g['left_cost']:.6f}→${g['right_cost']:.6f}({fr}감소), 같은쌍정답{g['paired_left_correct']}→{g['paired_right_correct']}.")
    lines+=['','실패를제외한정확도를대표수치로사용하지않았다. 짝이있는사용량의감소율은별도이며VM요금절감률이아니다. C의빈도상위5문자열과D1의다양성대표3문자열은의미정보량도다르므로단순압축효율만비교한것이아니다. 짧은모델근거는출력설명이며내부판단과정의증거가아니다.',
        '', '| 전환 | 조건 | 원본 | 변화 | 왼쪽상태/대상 | 오른쪽상태/대상 |', '|---|---|---|---|---|---|']
    for v in allpairs:
        if v['left_correct']==v['right_correct']:continue
        vals=[v['left']+'→'+v['right'],v['condition'],v['source'],'개선' if v['right_correct'] else '악화',str(v['left_category'])+'/'+str(v['left_target']),str(v['right_category'])+'/'+str(v['right_target'])]
        lines.append('|'+ '|'.join(str(x).replace('|','/') for x in vals)+'|')
    lines+=['','## 실행·사용량·비용·실패','',f"공통추가실행현황 `{c.global_status()}`. 개발60/최종360이예정이고제품통합연결은별도기록한다. 원요청/전체HTTP응답/해시/원usage/최초추천은runs/product-quality-v1에있다. SDK attempts1(원요청포함), 자동재추론0, 미확정이있으면동일ID회수전다음제출차단. 완료슬롯을새ID로교체하지않는다. USD10은코드추정예산이며청구하드캡이아니다. 단가1.5/7.5는보수적할인전표준참조, 현재한시공시0.75/3.75도구분한다. output+thinking은total-prompt로한번계산하고캐시/크레딧차감0. 실제청구·세금·잔여크레딧미확인. [공식가격](https://cloud.google.com/model-garden/pricing).",
        '', '| 방법 | 입력(제공/누락 포함) | 출력 | 추론 | 캐시 | API관측합초 | 로컬전체합초 | 참조USD |', '|---|---|---|---|---|---|---|---|']
    for g in final['totals']:
        if g['method']=='A':continue
        lines.append('|'+ '|'.join([g['method']]+[str(g[k]) for k in ('input_tokens','output_tokens','thought_tokens','cached_input_tokens','model_call_seconds','local_total_seconds','cost_usd')])+'|')
    lines+=['',f"실패목록 `{failed}`. 서버내부처리/로딩시간은API미제공이며SDK호출시간만측정했다. 프로파일/토큰사전계산은별도여서SDK시간에과거계산시간을넣지않았다. 모델/방법순서는사전순환이지만캐시·가용성·단회조건때문에통계적속도우위를증명하지않는다.",
        '', '## 제품 반영과 남은 조건','',f"기본방법 {default}, D1선택규칙충족 {qualify}. 앱에서B/C/D1을명시적으로선택하고실제로사용한정보·대표값·제외이유·모호항목을확인한다. 원본값/선행0·최초추천/사용자수정분리·중복대상충돌차단·확정/다운로드를유지했다. 저장된실행결과에는시각·방법·모델을표시하며재호출하지않는다. 실시간연구실행중서비스호출은차단한다.",
        '기본상품/주문서비스는구성된6대상전체를후보로쓰지만공개T2D평가는일부주석후보다. 이점수를그대로서비스전체정확도라고하지않는다. 대상참조CSV가없으면대상프로파일을만들지않고메타데이터만써서양쪽프로파일의연구설정과도다름을화면에표시한다. 별도실제거래처원본·확정정답·미대응/분포이동·단위/금액·설명누락·한영혼용·국내자료·여러모델/반복·보안/개인정보/이용조건·대규모장애운영은상용화전추가검증이필요하다.',
        '이번평가는기존자료와분리한30계열·단일모델·단회·주석/생성계보범위의제품후보검증이다. 전체벤치마크나상용화조건을모두입증한것이아니다. 결과를본뒤추가튜닝이나후속실험을시작하지않았다. Azure VM은할당해제상태를유지하며새유료인프라/모델을만들지않았다.',
        '', '## 재현·저장 결과 확인','', '```powershell\n.\\.venv\\Scripts\\python.exe scripts/run_product_quality.py status\n.\\.venv\\Scripts\\python.exe scripts/run_product_quality.py score --phase development\n.\\.venv\\Scripts\\python.exe scripts/run_product_quality.py score --phase evaluation\n.\\.venv\\Scripts\\python.exe scripts/report_product_quality.py\n.\\start-gcp.ps1\n```',
        'status/score/report는신규추론0회다. 중단된실행은기존ID의상태/완료HTTP부터확인하고동일계획의미실행슬롯만run으로재개한다. 완료/실패를성공할때까지반복하지않는다.']
    s.atomic(c.ROOT/'PRODUCT_QUALITY_REPORT.md','\n'.join(lines).encode('utf-8'))
    print(json.dumps({'default':default,'criterion_satisfied':qualify,'totals':[{k:g[k] for k in ('method','correct','planned','auto_links','correct_auto_links','auto_link_coverage','categories')} for g in final['totals']],'comparisons':comparisons,'new_inferences':0},ensure_ascii=True))

if __name__=='__main__':main()
