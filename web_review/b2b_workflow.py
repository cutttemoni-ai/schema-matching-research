"""Authenticated, persistent supplier rules and snapshot-bound B2B approvals.

CAS state is the execution lock. Each approval has immutable inputs/plans/files;
changed answers invalidate the preview and old downloads. No background retry.
"""
import base64
from copy import deepcopy
from decimal import InvalidOperation
import json
import re
import uuid
from schema_match.cloud_c_service import checked_csv, evidence
from schema_match.models import Column
from schema_match.records import now_iso
from schema_match.vertex_provider_v1 import digest
from .storage import read_json, immutable, InferenceStore, Conflict
from .service import WorkflowError, identifier, sha
from .transforms import csvbytes
from .b2b_contract import standards, clean_bindings, compile_binding, signature, VERSION
from .b2b_precision import apply, VERSION as PRECISION_VERSION


class B2BWorkflow:
    def __init__(self, objects, rule_objects=None, infer=None):
        self.objects=objects;self.rules=rule_objects or objects;self.infer=infer

    def supplier_key(self,uid,supplier):
        return f'b2b-rules-v1/users/{identifier(uid)}/suppliers/{identifier(supplier)}.json'

    def supplier(self,uid,supplier):
        value,generation=read_json(self.rules,self.supplier_key(uid,supplier))
        if not value or value.get('owner_id')!=uid:raise WorkflowError('거래처를 찾을 수 없습니다.',404)
        return value,generation

    def suppliers(self,uid):
        out=[]
        for key in self.rules.keys(f'b2b-rules-v1/users/{identifier(uid)}/suppliers/'):
            value,_=read_json(self.rules,key)
            if value and value.get('owner_id')==uid:
                out.append(dict(id=value['id'],name=value['name'],created_at=value['created_at'],
                                versions=[{k:r[k] for k in ('version','kind','approved_at','approval_id','schema_hash','rule_id')} for r in value['history']]))
        return sorted(out,key=lambda x:x['created_at'])

    def register_supplier(self,uid,name,nonce):
        identifier(nonce)
        if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise WorkflowError('거래처명은 1~80자입니다.')
        sid=digest([uid,nonce,'supplier'])[:32];key=self.supplier_key(uid,sid)
        value=dict(id=sid,owner_id=uid,name=name.strip(),created_at=now_iso(),history=[])
        existing,_=read_json(self.rules,key)
        if existing:
            if existing['name']!=value['name']:raise WorkflowError('같은 등록 요청의 거래처명이 달라졌습니다.',409)
            return existing
        immutable(self.rules,key,value)
        return value

    def prefix(self,uid,tid):return f'b2b-web-v1/users/{identifier(uid)}/tasks/{identifier(tid)}/'
    def load(self,uid,tid):
        v,g=read_json(self.objects,self.prefix(uid,tid)+'state.json')
        if not v or v.get('owner_id')!=uid:raise WorkflowError('작업을 찾을 수 없습니다.',404)
        return v,g
    def write(self,v,g):return self.objects.write(self.prefix(v['owner_id'],v['task_id'])+'state.json',v,g)

    def inputs(self,v):
        raw=self.objects.read(self.prefix(v['owner_id'],v['task_id'])+'source.csv')[0]
        if raw is None or sha(raw)!=v['source_sha256']:raise WorkflowError('원본 파일 무결성 오류입니다.',409)
        source=checked_csv(raw)
        rows=[{c.id:str(row[c.name]) for c in source.columns} for row in source.frame.to_dict(orient='records')]
        return source,rows,raw

    def list(self,uid):
        out=[]
        for key in self.objects.keys(f'b2b-web-v1/users/{identifier(uid)}/tasks/'):
            if key.endswith('/state.json'):
                v,_=read_json(self.objects,key)
                if v and v['owner_id']==uid:out.append({k:v[k] for k in ('task_id','source_name','supplier_name','kind','phase','created_at','row_count')})
        return sorted(out,key=lambda x:x['created_at'],reverse=True)

    def create(self,owner,p,nonce):
        uid=identifier(owner['uid']);identifier(nonce);vendor,_=self.supplier(uid,p.get('supplier_id'))
        schema=standards(p.get('kind'));schema_hash=digest(schema)
        try:raw=base64.b64decode(p['source_b64'],validate=True)
        except (KeyError,ValueError,TypeError):raise WorkflowError('CSV 파일을 확인해 주세요.')
        name=p.get('source_name','source.csv')
        if not isinstance(name,str) or not 1<=len(name)<=200:raise WorkflowError('파일 이름을 확인해 주세요.')
        source=checked_csv(raw);rows=[{c.id:str(r[c.name]) for c in source.columns} for r in source.frame.to_dict(orient='records')]
        tid=digest([uid,nonce,'b2b-web'])[:32];existing,_=read_json(self.objects,self.prefix(uid,tid)+'state.json')
        input_hash=digest([sha(raw),vendor['id'],schema_hash,name])
        if existing:
            if existing['input_hash']!=input_hash:raise WorkflowError('동일 요청에 다른 파일을 등록할 수 없습니다.',409)
            return self.public(uid,tid)
        bindings=[dict(key=uuid.uuid4().hex,source_ids=[c.id],target_id=None,operation='scalar',answers={},scope='file',mapping_confirmed=False,exclude=False) for c in source.columns]
        v=dict(task_id=tid,owner_id=uid,supplier_id=vendor['id'],supplier_name=vendor['name'],kind=p['kind'],schema=schema,schema_hash=schema_hash,
               source_name=name,source_sha256=sha(raw),input_hash=input_hash,created_at=now_iso(),updated_at=now_iso(),
               version=1,decisions_version=1,phase='draft',bindings=bindings,initial_result=None,inference_state='not_started',
               row_count=len(rows),execution_count=0,active_approval=None,preview=None,reuse=None)
        sig=signature(source.columns,rows);names={c.id:c.name for c in source.columns}
        candidates=[r for r in reversed(vendor['history']) if r['kind']==p['kind'] and r['schema_hash']==schema_hash]
        # Latest approved rule for this EXACT source shape only; never fall back
        # to an older rule when the latest compatible revision was invalidated.
        saved=next((r for r in candidates if set(r['signature'])==set(sig)),None)
        if saved:
            v['bindings']=deepcopy(saved['bindings'])
            old_ids=saved['column_names'];new_ids={c.name:c.id for c in source.columns}
            def remap(value):
                if isinstance(value,dict):return {k:remap(x) for k,x in value.items()}
                if isinstance(value,list):return [remap(x) for x in value]
                return new_ids[old_ids[value]] if isinstance(value,str) and value in old_ids else value
            v['bindings']=remap(v['bindings'])
            affected=[]
            for b in v['bindings']:
                if saved.get('engine_version')!=VERSION or saved.get('precision_version')!=PRECISION_VERSION:
                    b['mapping_confirmed']=False
                    affected.append(dict(key=b['key'],reason='계산 기준 버전이 바뀌어 연결·변환을 다시 확인해야 합니다.'))
                if b['scope']!='format':
                    b.update(answers={},mapping_confirmed=False,exclude=False);affected.append(dict(key=b['key'],reason='이전 확인은 그 파일에만 적용됩니다.'))
                    continue
                relevant=set(b['source_ids'])|{b['answers'].get(k) for k in ('unit_column','pack_column','rate_column') if b['answers'].get(k)}
                changed=[i for i in relevant if not set(sig[names[i]])<=set(saved['signature'][names[i]])]
                # Explicitly retained pack/unit domains are business facts; new
                # categories/pack values require new confirmation, even if valid.
                for key in ('unit_column','pack_column','rate_column'):
                    ref=b['answers'].get(key)
                    if ref:
                        domain={r[ref] for r in rows}
                        if not domain<=set(saved.get('domains',{}).get(names[ref],[])):
                            changed.append(ref)
                            if key=='pack_column':b['answers'].pop('pack_mode',None)
                            elif key=='unit_column':b['answers'].pop('basis',None)
                            else:b['answers'].pop('rate_column',None)
                if changed:
                    b['mapping_confirmed']=False
                    affected.append(dict(key=b['key'],reason='자료형·값 형식·단위 또는 입수가 바뀌었습니다.'))
            v.update(phase='review',inference_state='reused_rule',reuse=dict(rule_id=saved['rule_id'],version=saved['version'],
                     approved_at=saved['approved_at'],affected=affected,all_rows_validated=True))
        elif candidates:
            v['reuse']=dict(version=candidates[0]['version'],affected=[dict(key=None,reason='열 구성이 바뀌어 저장 규칙을 적용하지 않았습니다.')],all_rows_validated=False)
        immutable(self.objects,self.prefix(uid,tid)+'source.csv',raw)
        self.write(v,0)
        return self.public(uid,tid)

    def evaluation(self,v):
        source,rows,_=self.inputs(v);fields={f['id']:f for f in v['schema']['fields']}
        results=[compile_binding(b,fields,rows,source.columns) for b in v['bindings']]
        declared_packs=[(b,r) for b,r in zip(v['bindings'],results) if b['target_id'] and b['mapping_confirmed']
                        and fields[b['target_id']]['unit_contract'].get('dimension')=='EA/BOX' and r['conversion_readiness']=='ready']
        for b,r in zip(v['bindings'],results):
            if b['answers'].get('pack_mode')!='fixed' or r['conversion_readiness']!='ready':continue
            for pb,pr in declared_packs:
                for index,row in enumerate(rows):
                    if apply(pr['recipe'],row)!=b['answers']['pack']:
                        # Compare values numerically without binary floats.
                        from decimal import Decimal
                        if Decimal(apply(pr['recipe'],row))!=Decimal(b['answers']['pack']):
                            r['errors'].append(dict(row_number=index+2,reason='확인한 고정 입수와 박스당 입수 열이 충돌합니다.'))
                if r['errors']:r['conversion_readiness']='needs_review'
        issues=[];targets={};included=[];excluded=[]
        for b,r in zip(v['bindings'],results):
            if b['target_id']:
                targets.setdefault(b['target_id'],[]).append(b['key'])
                if r['mapping_status']!='matched':issues.append(dict(key=b['key'],message='연결 의미를 담당자가 확인해 주세요.'))
                if r['conversion_readiness']!='ready':issues.append(dict(key=b['key'],message='변환에 필요한 답변 또는 전체 행 검사가 완료되지 않았습니다.'))
                included.append((b,r))
            elif not b['exclude']:issues.append(dict(key=b['key'],message='연결 대상을 선택하거나 명시적으로 제외해 주세요.'))
            else:excluded.append(dict(source_ids=b['source_ids'],reason='담당자가 연결 제외를 확인했습니다.'))
        for target,keys in targets.items():
            if len(keys)>1:issues.append(dict(key=None,message=fields[target]['name']+'에 연결이 중복됩니다. 복합 연결로 묶거나 수정해 주세요.'))
        for f in fields.values():
            if f['required'] and f['id'] not in targets:issues.append(dict(key=None,message=f['name']+' 필수 항목이 빠졌습니다.'))
        if v['inference_state'] in ('running','uncertain'):issues.append(dict(key=None,message='추천 완료 여부를 확인할 수 없습니다. 기존 요청부터 확인해 주세요.'))
        outputs=[];samples=[]
        headers=[f['name'] for f in fields.values() if f['id'] in targets]
        ordered=[next(((b,r) for b,r in included if b['target_id']==f['id']),None) for f in fields.values() if f['id'] in targets]
        for index,row in enumerate(rows):
            output=[]
            for b,r in ordered:
                value='[변환 확인 필요]'
                if r['conversion_readiness']=='ready':
                    value=apply(r['recipe'],{**row,'confirmed_rate_'+b['key']:b['answers'].get('rate','')})
                output.append(value)
                if index<5:samples.append(dict(key=b['key'],row_number=index+2,source_values=[row[i] for i in b['source_ids']],value=value))
            outputs.append(output)
        absent=[f['name'] for f in fields.values() if f['id'] not in targets]
        return dict(results=results,issues=issues,headers=headers,rows=outputs,samples=samples,
                    excluded=excluded,absent_targets=absent,total_rows=len(rows),source=source)

    def public(self,uid,tid):
        v,_=self.load(uid,tid);source,rows,_=self.inputs(v);ev=self.evaluation(v)
        out=deepcopy(v);out.pop('input_hash',None)
        out['columns']=[dict(id=c.id,name=c.name,examples=list(dict.fromkeys(r[c.id] for r in rows))[:3]) for c in source.columns]
        out['assessments']=ev['results'];out['issues']=ev['issues']
        return out

    def save(self,uid,tid,p):
        v,g=self.load(uid,tid)
        if v['phase'] in ('executing','inferencing'):raise WorkflowError('처리 중에는 변경할 수 없습니다.',423)
        if p.get('version')!=v['version']:raise WorkflowError('다른 창에서 변경됐습니다. 다시 열어 주세요.',409)
        source,_,_=self.inputs(v);bindings=clean_bindings(p.get('bindings'),source.columns,v['schema'])
        if bindings==v['bindings']:return self.public(uid,tid)
        immutable(self.objects,self.prefix(uid,tid)+f'history/{v["version"]:06}.json',v)
        v.update(bindings=bindings,decisions_version=v.get('decisions_version',v['version'])+1,version=v['version']+1,phase='review',preview=None,active_approval=None,updated_at=now_iso())
        self.write(v,g)
        return self.public(uid,tid)

    def recommend(self,owner,tid,version):
        uid=owner['uid'];v,g=self.load(uid,tid)
        if v['initial_result'] is not None:return self.public(uid,tid),True
        if v['inference_state'] in ('running','uncertain'):raise WorkflowError('기존 추천 요청이 진행 중이거나 완료 미확정입니다. 새 요청을 만들지 않습니다.',409)
        if v['phase']=='completed' or (v.get('reuse') or {}).get('rule_id'):
            raise WorkflowError('저장 규칙을 적용한 작업은 직접 검토하세요. 새 추천은 새 파일 작업에서 실행합니다.',409)
        if version!=v['version']:raise WorkflowError('작업 버전을 확인해 주세요.',409)
        v.update(phase='inferencing',inference_state='running',version=v['version']+1,preview=None,active_approval=None)
        self.write(v,g);source,rows,raw=self.inputs(v)
        target=[Column(**{k:f[k] for k in ('id','name','description','data_type')}) for f in v['schema']['fields']]
        wire=evidence(source,target)
        wire.update(business_context={'standard_id':v['schema']['schema_id'],'row_grain':v['kind'],
                                     'source_headers':[c.name for c in source.columns],'scope':'Semantic mapping only; business facts require human confirmation'},
                    b2b_web_engine='v3-web-recommendation-1')
        store=InferenceStore(self.objects,uid,tid)
        try:
            if self.infer:result,_=self.infer(store,wire,raw,None)
            else:
                from .b2b_inference import recommend
                result,_=recommend(store,wire,raw)
        except Exception as e:
            # Unknown completion must NEVER be relabelled as no-match or retried.
            result=dict(status='uncertain',error='추천 완료 확인 필요: '+type(e).__name__,request_id=uuid.uuid4().hex,physical_POST_attempts=None)
        immutable(self.objects,self.prefix(uid,tid)+'initial.json',result)
        current,g=self.load(uid,tid)
        current['initial_result']=deepcopy(result)
        current['inference_state']='completed' if result.get('status')=='success' else 'uncertain' if result.get('status')=='uncertain' else 'failed'
        recs={m['source_id']:m for m in result.get('raw_recommendations',result.get('initial_recommendations',[]))}
        for b in current['bindings']:
            r=recs.get(b['source_ids'][0])
            if r and (r.get('target_id') is None or r.get('target_id') in {f['id'] for f in current['schema']['fields']}):
                if b['target_id']!=r.get('target_id'):b['answers']={}
                b['target_id']=r.get('target_id');b['mapping_confirmed']=False;b['exclude']=False
        current.update(phase='review',decisions_version=current.get('decisions_version',current['version'])+1,version=current['version']+1)
        self.write(current,g)
        return self.public(uid,tid),False

    def snapshot(self,v,ev):
        return digest(dict(source=v['source_sha256'],schema=v['schema_hash'],supplier=v['supplier_id'],kind=v['kind'],
                           decisions_version=v.get('decisions_version',v['version']),bindings=v['bindings'],plans=ev['results'],contract=VERSION,precision=PRECISION_VERSION))

    def preview(self,uid,tid,version):
        v,g=self.load(uid,tid)
        if version!=v['version']:raise WorkflowError('변경 후 다시 미리보기해 주세요.',409)
        if v['phase']=='executing':raise WorkflowError('기존 실행을 확인해 주세요.',409)
        ev=self.evaluation(v);token=self.snapshot(v,ev)
        preview=dict(token=token,version=v['version'],can_approve=not ev['issues'],headers=ev['headers'],rows=ev['rows'][:20],samples=ev['samples'],
                     issues=ev['issues'],excluded=ev['excluded'],absent_targets=ev['absent_targets'],assessments=ev['results'],
                     all_rows_checked=ev['total_rows'],excluded_rows=0,
                     error_count=sum(len(r['errors']) for r in ev['results']))
        immutable(self.objects,self.prefix(uid,tid)+'previews/'+token+'.json',{k:x for k,x in preview.items() if k!='version'})
        v['preview']={'token':token,'version':v['version']};self.write(v,g)
        return preview

    def _publish_rule(self,v,ev,approval):
        if not any(b['scope']=='format' for b in v['bindings']):return None
        uid=v['owner_id'];vendor,g=self.supplier(uid,v['supplier_id'])
        existing=next((r for r in vendor['history'] if r['approval_id']==approval['approval_id']),None)
        if existing:return existing['version']
        source,rows,_=self.inputs(v);domains={}
        for b in v['bindings']:
            if b['scope']=='format':
                for key in ('unit_column','pack_column','rate_column'):
                    ref=b['answers'].get(key)
                    if ref:domains[next(c.name for c in source.columns if c.id==ref)]=sorted({r[ref] for r in rows})
        revision=dict(rule_id=digest([v['supplier_id'],v['kind'],v['schema_hash'],signature(source.columns,rows)])[:32],
                      version=len(vendor['history'])+1,kind=v['kind'],schema_hash=v['schema_hash'],schema_version=v['schema']['version'],
                      signature=signature(source.columns,rows),column_names={c.id:c.name for c in source.columns},domains=domains,
                      bindings=deepcopy(v['bindings']),approved_plans=deepcopy(ev['results']),approval_id=approval['approval_id'],
                      approved_at=approval['approved_at'],approved_by=uid,source_sha256=v['source_sha256'],
                      previous_version=vendor['history'][-1]['version'] if vendor['history'] else None,
                      engine_version=VERSION,precision_version=PRECISION_VERSION)
        vendor['history'].append(revision)
        self.rules.write(self.supplier_key(uid,v['supplier_id']),vendor,g)
        return revision['version']

    def approve(self,owner,tid,version,token):
        uid=owner['uid'];v,g=self.load(uid,tid)
        if v['active_approval'] and v['active_approval']['snapshot']==token:
            return self.public(uid,tid),True
        if v['phase'] in ('executing','inferencing'):raise WorkflowError('기존 실행이 끝났는지 확인해 주세요.',409)
        if version!=v['version'] or not v['preview'] or v['preview']['token']!=token:
            raise WorkflowError('이 파일·답변으로 다시 미리본 후 승인해 주세요.',409)
        ev=self.evaluation(v)
        if token!=self.snapshot(v,ev):raise WorkflowError('규칙 또는 변환 기준이 바뀌었습니다. 다시 미리보기해 주세요.',409)
        if ev['issues']:raise WorkflowError('미응답·충돌·행 오류를 해결하기 전에는 실행할 수 없습니다.',422,{'issues':ev['issues']})
        aid=digest([uid,tid,token])[:32]
        approval=dict(approval_id=aid,snapshot=token,approved_by=uid,approved_username=owner['username'],approved_at=now_iso(),
                      source_sha256=v['source_sha256'],schema_hash=v['schema_hash'],version=v['version'],bindings=deepcopy(v['bindings']),
                      plans=ev['results'],contract_version=VERSION,precision_version=PRECISION_VERSION,status='running')
        v.update(phase='executing',active_approval=approval,version=v['version']+1,execution_count=v['execution_count']+1)
        self.write(v,g)  # single process/instance owns the execution from here
        prefix=self.prefix(uid,tid)+'approvals/'+aid+'/'
        immutable(self.objects,prefix+'approval.json',approval)
        try:
            source=ev['source'];used={s for b in v['bindings'] if b['target_id'] for s in b['source_ids']}
            unused=[c for c in source.columns if c.id not in used]
            files={'standardized.csv':csvbytes(ev['headers'],ev['rows']),
                   'unmapped.csv':csvbytes([c.name for c in unused],[[str(row[c.name]) for c in unused] for row in source.frame.to_dict(orient='records')]),
                   'mapping.csv':csvbytes(['원본 열','표준 항목','적용 규칙','확인 적용 범위'],
                       [[' + '.join(next(c.name for c in source.columns if c.id==i) for i in b['source_ids']),
                         next((f['name'] for f in v['schema']['fields'] if f['id']==b['target_id']),'연결 제외'),
                         ' / '.join(r['explanations']), '이 형식에 계속' if b['scope']=='format' else '이번 파일만'] for b,r in zip(v['bindings'],ev['results'])])}
            for filename,raw in files.items():immutable(self.objects,prefix+filename,raw)
            rule_version=self._publish_rule(v,ev,approval)
            receipt={**approval,'status':'completed','result_files':{n:sha(raw) for n,raw in files.items()},'supplier_rule_version':rule_version,
                     'row_count':ev['total_rows'],'excluded_rows':0,'excluded':ev['excluded'],'absent_targets':ev['absent_targets'],
                     'completed_at':now_iso()}
            immutable(self.objects,prefix+'receipt.json',receipt)
            current,g=self.load(uid,tid);current.update(active_approval=receipt,phase='completed',updated_at=now_iso())
            self.write(current,g)
        except Exception:
            # Durable running state is deliberately not retried: some files/rule
            # may already have committed. Administrative reconciliation required.
            raise WorkflowError('실행 또는 저장 완료를 확인하지 못했습니다. 같은 작업을 반복 실행하지 말고 실행 기록을 확인해 주세요.',503)
        return self.public(uid,tid),False

    def download(self,uid,tid,aid,filename):
        v,_=self.load(uid,tid);a=v.get('active_approval')
        if v['phase']!='completed' or not a or aid!=a['approval_id']:raise WorkflowError('현재 승인된 결과가 아닙니다. 다시 확인해 주세요.',409)
        if filename not in ('standardized.csv','unmapped.csv','mapping.csv','receipt.json'):raise WorkflowError('파일을 찾을 수 없습니다.',404)
        raw=self.objects.read(self.prefix(uid,tid)+'approvals/'+identifier(aid)+'/'+filename)[0]
        if raw is None or filename!='receipt.json' and sha(raw)!=a['result_files'][filename]:raise WorkflowError('결과 파일 무결성 오류입니다.',409)
        if filename=='receipt.json' and json.loads(raw)!=a:raise WorkflowError('승인 기록 무결성 오류입니다.',409)
        return raw
