"""Offline scoring of the sealed main30 campaign. Never creates a model client."""
import csv,io,json
from collections import Counter
from datetime import datetime
from . import gemini_main30 as study
from .config import ROOT
from .records import now_iso

TOKENS={'input_tokens':'prompt_token_count','output_tokens':'candidates_token_count',
        'thought_tokens':'thoughts_token_count','cached_input_tokens':'cached_content_token_count','total_tokens':'total_token_count'}


def judge(record,kind,expected,pending=False):
    if record is None:return {'category':'uncertain' if pending else 'unexecuted','correct':False,'status':None,'target_id':None,'reason':None}
    if record['execution_category']!='valid_output':
        return {'category':record['execution_category'],'correct':False,'status':None,'target_id':None,'reason':None}
    prediction=record['policy_recommendations'][0]
    correct=(prediction['status']=='matched' and prediction['target_id']==expected) if kind=='main' else (prediction['status']=='no_match' and prediction['target_id'] is None)
    return dict(prediction,correct=correct,category='correct' if correct else 'needs_review' if prediction['status']=='needs_review' else 'semantic_error')


def observed(rows,key):
    vals=[r[key] for r in rows if r.get(key) is not None]
    return {'sum':sum(vals),'observed_n':len(vals),'missing_n':len(rows)-len(vals)}


def aggregate(rows):
    n=len(rows);correct=sum(r['correct'] for r in rows)
    g={'planned':n,'correct':correct,'top1':correct/n if n else None,'categories':dict(Counter(r['category'] for r in rows)),
       'valid_outputs':sum(r['execution_category']=='valid_output' for r in rows),
       'resolved':sum(r['category'] not in ('uncertain','unexecuted') for r in rows)}
    for kind in ('main','natural_none'):
        sub=[r for r in rows if r['task_kind']==kind]
        g[kind]={'correct':sum(r['correct'] for r in sub),'planned':len(sub),
            'wrong_links':sum(r['category']=='semantic_error' and r['status']=='matched' for r in sub)}
    for key in (*TOKENS,'model_call_seconds','local_total_seconds','no_discount_cost_usd'):
        g[key]=observed(rows,key)
    return g


def csv_bytes(rows):
    out=io.StringIO(newline='');fields=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(out,fieldnames=fields);w.writeheader()
    for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
    return out.getvalue().encode('utf-8-sig')


def write_report():
    # The driver lock prevents reading truth concurrently with a generation loop.
    from infra.remote_executor_v3 import locked
    with locked(study.RUNS/'driver.lock'):
        p=study.verify();rows=[];tasks={t['task_id']:t for t in p['selected_tasks']}
        annotation=ROOT/'datasets/wdc_smb/raw/t2d_sm_wh/test/test_correspondences.csv'
        if study.filehash(annotation)!=p['annotation_sha256_for_evaluation_only']:raise ValueError('Truth hash changed')
        annotations=list(csv.DictReader(io.StringIO(annotation.read_text(encoding='utf-8-sig'))))
        for row in annotations:
            for key in ('column_index_left','column_index_right','label'):row[key]=int(row[key])
        from scripts.gcp_public_score import truth_for_plan
        truth=truth_for_plan(p,annotations)
        bytask={t['task_id']:next(j for j in p['jobs'] if j['task_id']==t['task_id']) for t in p['selected_tasks']}
        for j in p['jobs']:
            t=tasks[j['task_id']];r=study.read_result(j);d=study.jobdir(j)
            if r and (r.get('request_id')!=j['id'] or r.get('request')!=j['wire']):raise ValueError('Request/result mismatch')
            if r and (d/'http-complete.json').exists():
                receipt=study.read(d/'http-complete.json');raw=(d/'http-response.bin').read_bytes()
                if len(raw)!=receipt['bytes'] or study.sha256(raw).hexdigest()!=receipt['sha256']:raise ValueError('HTTP completeness mismatch')
            state=judge(r,t['kind'],truth[t['task_id']],(d/'slot.json').exists())
            u=(r or {}).get('usage') or {};name=p['headers_for_offline_evaluation_only'][t['pair_id']]['source'][t['source_index']]
            candidate_names={v['id']:v['name'] for v in j['wire']['target_fields']}
            rows.append({k:j[k] for k in ('id','order','task_id','condition','method','profile_type','metadata_type')}|state|{
                'pair_id':t['pair_id'],'source_index':t['source_index'],'component_id':t['component_id'],'source_name_original':name,
                'task_kind':t['kind'],'expected_id':truth[t['task_id']],'target_name':candidate_names.get(state['target_id']),
                'expected_name':candidate_names.get(truth[t['task_id']]),'candidate_names':candidate_names,
                'execution_category':(r or {}).get('execution_category',state['category']),
                'raw_response':(r or {}).get('raw_response'),'error':(r or {}).get('error'),'usage_raw':u,
                **{key:u.get(field) for key,field in TOKENS.items()},
                'no_discount_cost_usd':((r or {}).get('no_discount_cost') or {}).get('amount'),
                'model_call_seconds':(r or {}).get('model_call_seconds'),'local_total_seconds':(r or {}).get('local_total_seconds'),
                'recovered_HTTP':(r or {}).get('recovered_from_saved_HTTP'),'http_status':(r or {}).get('http_status')})
        for ar in p['A_local']:
            t=tasks[ar['task_id']];j=bytask[ar['task_id']];r={'execution_category':'valid_output','policy_recommendations':ar['recommendations']}
            rows.append({'id':'A-'+ar['task_id']+'-'+ar['condition'],'task_id':ar['task_id'],'condition':ar['condition'],'method':'A',
                'pair_id':t['pair_id'],'component_id':t['component_id'],'source_index':t['source_index'],
                'source_name_original':p['headers_for_offline_evaluation_only'][t['pair_id']]['source'][t['source_index']],
                'task_kind':t['kind'],'profile_type':j['profile_type'],'metadata_type':j['metadata_type'],'expected_id':truth[t['task_id']],
                **judge(r,t['kind'],truth[t['task_id']]),'execution_category':'valid_output','model_calls':0,'local_total_seconds':ar['elapsed_seconds'],
                'no_discount_cost_usd':0.})
        groups=[{'condition':c,'method':m,**aggregate([r for r in rows if r['method']==m and r['condition']==c])} for c in study.CONDITIONS for m in 'ABCD']
        totals=[{'method':m,**aggregate([r for r in rows if r['method']==m])} for m in 'ABCD']
        types=[{'profile_type':typ,'method':m,'condition':c,**aggregate([r for r in rows if r['method']==m and r['condition']==c and ('numeric' if r['profile_type'] in ('number','integer') else r['profile_type'])==typ])}
            for typ in ('numeric','string') for c in study.CONDITIONS for m in 'ABCD']
        lookup={(r['task_id'],r['condition'],r['method']):r for r in rows};pairs=[]
        for t in p['selected_tasks']:
            for c in study.CONDITIONS:
                for left,right in (('B','C'),('B','D'),('C','D')):
                    l=lookup[t['task_id'],c,left];r=lookup[t['task_id'],c,right]
                    pair={'task_id':t['task_id'],'source_name':l['source_name_original'],'condition':c,'left':left,'right':right,
                        'left_category':l['category'],'right_category':r['category'],'left_correct':l['correct'],'right_correct':r['correct'],
                        'improved':not l['correct'] and r['correct'],'worsened':l['correct'] and not r['correct'],
                        'left_status':l['status'],'right_status':r['status'],'left_reason':l['reason'],'right_reason':r['reason']}
                    for key in ('input_tokens','no_discount_cost_usd'):
                        pair['left_'+key]=l.get(key);pair['right_'+key]=r.get(key)
                    pairs.append(pair)
        comparisons=[]
        for l,r in (('B','C'),('B','D'),('C','D')):
            sub=[v for v in pairs if v['left']==l and v['right']==r];g={'left':l,'right':r,'planned_pairs':len(sub),
                'improved':sum(v['improved'] for v in sub),'worsened':sum(v['worsened'] for v in sub)}
            for key in ('input_tokens','no_discount_cost_usd'):
                matched=[v for v in sub if v['left_'+key] is not None and v['right_'+key] is not None]
                a=sum(v['left_'+key] for v in matched);b=sum(v['right_'+key] for v in matched)
                g[key]={'paired_n':len(matched),'missing_pairs':len(sub)-len(matched),'left_sum':a,'right_sum':b,'reduction_ratio':(a-b)/a if a else None}
            comparisons.append(g)
        evidence=study.read(study.OUT/'profile-evidence.json');coverage={}
        for side in ('source','target'):
            cols=[v for v in evidence.values() if v['side']==side];features=[v['full_profile']['features'] for v in cols]
            coverage[side]={'unique_columns':len(cols),'inferred_types':dict(Counter(v['inferred_type'] for v in features)),
                'numeric_aggregates':sum('numeric_min' in f and 'q25' in f for f in features),
                'date_ranges':sum('date_min' in f for f in features),
                'feature_keys':dict(Counter(k for f in features for k in f))}
        progress=study.budget_status(p)
        transmissions=[study.read(study.jobdir(j)/'transmission.json') for j in p['jobs'] if (study.jobdir(j)/'transmission.json').exists()]
        result={'at':now_iso(),'version':p['version'],'plan_sha256':study.filehash(study.OUT/'plan.json'),'progress':progress,
            'groups':groups,'totals':totals,'type_groups':types,'paired_comparisons':comparisons,'pairs':pairs,'rows':rows,'profile_coverage':coverage,
            'price':p['rate'],'actual_invoice_confirmed':False,'server_internal_times_available':False,
            'first_attempt_at':min((v['at'] for v in transmissions),default=None),'last_result_at':max((study.read_result(j)['finished_at'] for j in p['jobs'] if study.read_result(j)),default=None),
            'new_inferences_by_reporting':0,'ground_truth_only_in_offline_scoring':True,'user_edits_used':False,'past_results_merged':False}
        study.atomic(ROOT/'GEMINI_EVALUATION_RESULTS.json',result)
        study.atomic(ROOT/'GEMINI_EVALUATION_RESULTS.csv',csv_bytes(rows))
        study.atomic(ROOT/'GEMINI_EVALUATION_PAIRS.csv',csv_bytes(pairs))
        study.atomic(study.OUT/'scoring.json',{'at':result['at'],'annotation_hash':study.filehash(annotation),'new_inferences':0,'planned_generation_rows':270,'A_rows':90})
        write_markdown(result,p)
        # Record exact used components for subsequent evaluation exclusion without editing old registries.
        study.atomic(study.OUT/'future-evaluation-exclusions.json',{'version':p['version'],'reason':'Model predictions and evaluation truth inspected in this evaluation; exclude known related components from future final tests',
            'task_ids':[t['task_id'] for t in p['selected_tasks']],'component_ids':sorted({t['component_id'] for t in p['selected_tasks']}),
            'pair_ids':sorted({t['pair_id'] for t in p['selected_tasks']})})
        print(json.dumps({'progress':progress,'totals':[{k:g[k] for k in ('method','correct','planned','categories')} for g in totals],'paired':comparisons},ensure_ascii=False))
        return result


def write_markdown(r,p):
    pr=r['progress'];llm=[v for v in r['rows'] if v['method']!='A'];total=aggregate(llm)
    lines=['# Gemini 공개 데이터 소규모 평가 결과','',f"평가 `{p['version']}` / 보고 UTC {r['at']}. 주석된 후보 집합 내 Top-1. 표본30원본·서로 다른 알려진 성분30개, 양성28(숫자5/문자열23)+자연 미대응2, 원본/축약/ID3조건, 방법별 단회. 같은 원본의3변형을 독립 표본으로 세지 않는다. 단일 Gemini3.8Flash/Vertex global/LOW/출력4096이다.",
        '',f"## 실행 범위\n\n예정270 생성, 실제POST 시도 marker {pr['physical_POST_attempt_markers']}. 실행 상태 `{pr['categories']}`. 자동추론재시도0. 별도 smoke/서비스추론0, 과거 Qwen·Gemini 개발 검증은 합산하지 않았다. A90로컬 별도. 시작 {r['first_attempt_at']}, 마지막 결과 {r['last_result_at']}. 저장된 전체HTTP 크기/해시와 요청ID를 오프라인 재검증했다.",
        '', '## 조건별 결과','', '| 조건 | 방법 | 정답/예정 | Top-1 | 양성 정답/28 | 자연 미대응 정답/2 | 검토 | 의미오답 | 출력오류 | API실패 | 미확정/미실행 | 유효출력 |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for g in r['groups']:
        c=g['categories'];lines.append(f"|{g['condition']}|{g['method']}|{g['correct']}/{g['planned']}|{g['top1']:.1%}|{g['main']['correct']}/{g['main']['planned']}|{g['natural_none']['correct']}/{g['natural_none']['planned']}|{c.get('needs_review',0)}|{c.get('semantic_error',0)}|{c.get('output_error',0)}|{c.get('api_failure',0)}|{c.get('uncertain',0)}/{c.get('unexecuted',0)}|{g['valid_outputs']}|")
    lines+=['','실패·검토·미실행도 예정 분모에 포함한다. 미확정/미실행은 의미오답이 아니다. 양성만의 정답과 자연 미대응을 분리했으며 자연 미대응 오연결은 matched의 오연결 수로 별도 JSON에 있다. 사용자 수정은 사용하지 않았다.',
        '', '## 사용량·관측 시간·비용','', '| 조건 | 방법 | 입력 | 출력 | 추론 | 캐시입력 | SDK호출초 | 로컬전체초 | 할인전USD |', '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    def metric(v,precision=0):return f"{v['sum']:.{precision}f} (관측{v['observed_n']}/누락{v['missing_n']})"
    for g in r['groups']:
        if g['method']=='A':continue
        lines.append('|'+ '|'.join([g['condition'],g['method']]+[metric(g[k],6 if k=='no_discount_cost_usd' else 3 if 'seconds' in k else 0) for k in ('input_tokens','output_tokens','thought_tokens','cached_input_tokens','model_call_seconds','local_total_seconds','no_discount_cost_usd')])+'|')
    lines +=['',f"현재 공시 한시단가는 입력0.75/출력·추론3.75 USD/M이지만, 본 예산·보고는 할인·크레딧을 배제한 표준참조 입력1.50/출력·추론7.50 USD/M을 사용했다. 캐시도 전체입력으로 계산하여 할인0. 관측 할인전 합${pr['observed_no_discount_cost_usd']:.6f}, 비용 미확정{pr['cost_unknown_requests']}건, 예약포함 예산점유${pr['budget_commitment_usd']:.6f}/10. 실제 Google 청구액·세금·크레딧·다른 서비스비는 미확인. 이 USD10은 앱 추정 제한이며 청구 하드캡이 아니다. [공식 단가](https://cloud.google.com/model-garden/pricing).",
        '', '제공된 원 usage는 JSON에 그대로 보존했다. 누락한 캐시/추론 구성값을0으로 채우지 않았다. 비용은 보고된 total−prompt를 출력·추론 합계로 한 번만 계산했다. 출력4096은 추론과 표시출력의 공유 상한이다. [공식 토큰 한도](https://ai.google.dev/gemini-api/docs/generate-content/thinking). SDK호출은 네트워크·인증/서버·전체응답 파일확정까지의 클라이언트 관측치다. 내부 서버 추론/프롬프트/추론토큰 시간은 API 미제공이며 분리 측정하지 못했다. 로컬전체는 슬롯처리·검증 포함, 이 합계는 요청 사이 작업/중단을 포함하는 벽시계 경과와 다르다. 캐시조건은 실측이며 속도 우위의 통계적 증명이 아니다.',
        '', '## 동일 문제의 변화','']
    for g in r['totals']:
        by={v['condition']:v for v in r['groups'] if v['method']==g['method']};o=by['original'];a=by['abbreviated'];i=by['opaque']
        lines.append(f"- {g['method']}: 원본{o['correct']}/30 → 축약{a['correct']}/30 ({(a['top1']-o['top1'])*100:+.1f}%p), ID{i['correct']}/30 ({(i['top1']-o['top1'])*100:+.1f}%p). 전체{g['correct']}/90은30원본의 반복조건 합계다.")
    for g in r['paired_comparisons']:
        t=g['input_tokens'];c=g['no_discount_cost_usd'];reduction='미산정' if t['reduction_ratio'] is None else f"{t['reduction_ratio']:.1%}"
        creduction='미산정' if c['reduction_ratio'] is None else f"{c['reduction_ratio']:.1%}"
        lines.append(f"- {g['left']}→{g['right']}: 정답으로 바뀜{g['improved']}, 정답에서 벗어남{g['worsened']}. 입력 관측쌍{t['paired_n']}/90·누락쌍{t['missing_pairs']}, {t['left_sum']}→{t['right_sum']}토큰 (감소{reduction}); 비용 관측쌍{c['paired_n']}/90·누락쌍{c['missing_pairs']}, ${c['left_sum']:.6f}→${c['right_sum']:.6f} (감소{creduction}).")
    lines+=['','아래 변화는 각 사례의 관측값이다. 전체 변화 목록은 GEMINI_EVALUATION_PAIRS.csv에 보존했다. 짧은 근거는 출력 설명이며 내부 판단 과정의 증거가 아니다.','', '| 전환 | 조건 | 원본명 | 변화 | 왼쪽 상태·근거 | 오른쪽 상태·근거 |', '|---|---|---|---|---|---|']
    for v in r['pairs']:
        if not(v['improved'] or v['worsened']):continue
        vals=[v['left']+'→'+v['right'],v['condition'],v['source_name'],'개선' if v['improved'] else '악화',str(v['left_status'])+': '+str(v['left_reason']),str(v['right_status'])+': '+str(v['right_reason'])]
        lines.append('|'+ '|'.join(str(x).replace('|','/').replace('\n',' ') for x in vals)+'|')
    lines+=['','## 자료형별 결과','', '| 프로파일형 | 조건 | 방법 | 정답/예정 | 양성 정답/예정 | 자연 미대응 정답/예정 |', '|---|---|---|---:|---:|---:|']
    for g in r['type_groups']:lines.append(f"|{g['profile_type']}|{g['condition']}|{g['method']}|{g['correct']}/{g['planned']}|{g['main']['correct']}/{g['main']['planned']}|{g['natural_none']['correct']}/{g['natural_none']['planned']}|")
    lines+=['',f"실제 계산된 특징 범위: `{r['profile_coverage']}`. unique_columns는30문제에서 중복 열ID를 제거한 수다. 숫자 효과는 실제 숫자 집계가 있는 원본에서만 논의한다. 원본 날짜 집계가 없는 경우 대상 날짜 특징의 존재만으로 날짜 원본 매칭 효과를 평가했다고 하지 않는다.",
        '', '## 해석·남은 한계','',
        '프로파일은 후보에 관한 추가 정보이며 C의 상위 범주에는 실제 문자열이 포함된다. D는 같은 계산 결과에서 고정 자료형 규칙으로 일부만 선택하며 범주 문자열을 제외한다. 따라서 C/D는 길이뿐 아니라 의미 정보량도 다르다. 숫자 분포·자료형 일치만으로 사업상 의미를 확정할 수 없다. C/D가 모두 실패한 사례도 상세 CSV에서 확인할 수 있으며 후속 가설로 남기고 평가 후 규칙은 바꾸지 않았다.',
        '정답 수가 같아도 동등성 입증이 아니다. 입력/추론 토큰의 감소를 과거 Azure VM 요금 절감이나 실제 청구액 절감으로 환산하지 않는다. 헤더 변형은 원본 쪽만이며 대상 후보는 같으므로 완전한 양쪽 메타데이터 손실을 평가한 것이 아니다.',
        '자료형 의도 표집·주석된 후보 집합·원본30개·단일 모델·방법별 단회·알려진 중복 범위의 한계가 있다. 전체 벤치마크 또는 일반화/상용 정확도를 입증하지 않았다. 원 데이터에 설명이 없어 설명 제거 효과를 측정하지 못했다. 한영 혼용·국내 데이터·미지 생성 계열 중복·실업무 분포·여러 모델/반복/통계 검증은 미평가다. 이전 Qwen 및 Gemini 개발 검증과 합산하지 않았고 점수 차이를 수정 효과로 해석하지 않는다.',
        '', '## 재현·보존','',
        '새 생성 없이 상태/채점을 확인한다. 계획 해시는 plan/seal.json, 요청별 실제 전송 JSON·전체 HTTP원문·크기/해시·최초 응답·usage·판정은 runs/gemini-main30-v1/jobs에 있다. 사용자 수정 기록은 별도 서비스에 그대로 보존한다. 과거297개 기록과 원본 데이터541파일 해시는 실행 전후 검증한다. Azure VM 할당 해제는 유지하며 새 리소스/배포/서비스 추론은 하지 않았다.',
        '```powershell\n.\\.venv\\Scripts\\python.exe scripts/run_gemini_evaluation.py status\n.\\.venv\\Scripts\\python.exe scripts/run_gemini_evaluation.py report\n```',
        '미실행이 있을 때만 동일 계획·동일ID에서 run으로 재개한다. 완료 슬롯을 다시 호출하지 않는다. 미확정이 있으면 새ID 재시도 없이 저장된 HTTP확정 파일부터 확인한다. 본 평가에 사용한30성분은 future-evaluation-exclusions.json에 기록했으며 이후 독립 최종평가에서 제외해야 한다. 이번 결과를 보고 추가 실험이나 규칙 조정을 자동 시작하지 않는다.']
    study.atomic(ROOT/'GEMINI_EVALUATION_RESULTS.md','\n'.join(lines).encode('utf-8'))
