"""Versioned human decisions, approval CAS and idempotent CSV execution.

All entry points require a server-authenticated owner. Task IDs never grant
access. Inference delegates to the unchanged C provider and global20/day guard.
"""
import base64,hashlib,json,re,time,uuid
from copy import deepcopy
from collections import Counter
from pathlib import Path
from schema_match.config import ROOT
from schema_match.cloud_c_service import checked_csv,evidence,run_file,load_saved,file_fingerprint
from schema_match.files import load_schema
from schema_match.models import Column,Recommendation
from schema_match.review import validate_recommendations
from schema_match.vertex_provider_v1 import digest,load_config
from schema_match.records import now_iso
from .storage import read_json,immutable,encode,Conflict,InferenceStore
from .transforms import Target,Rule,parse_targets,evaluate,files_for,csvbytes,TRANSFORMS,VERSION
from .conversion import connections,VERSION as ASSESSMENT_VERSION

class WorkflowError(Exception):
    def __init__(self,message,status=400,details=None):super().__init__(message);self.status=status;self.details=details or {}

def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-f0-9]{32}',value):raise WorkflowError('작업을 찾을 수 없습니다.',404)
    return value
def sha(raw):return hashlib.sha256(raw).hexdigest()
def default_targets():return [Target(**t.model_dump(),required=t.id in ('product_code','product_name')) for t in load_schema()]
def default_schema():return [t.model_dump() for t in default_targets()]

class Workflow:
    def __init__(self,objects,infer=None,executor=None):
        self.objects=objects;self.infer=infer or run_file;self.executor=executor or files_for
    def prefix(self,uid,task):return f'review-v2/users/{identifier(uid)}/tasks/{identifier(task)}/'
    def state_key(self,uid,task):return self.prefix(uid,task)+'state.json'
    def load(self,uid,task):
        v,gen=read_json(self.objects,self.state_key(uid,task))
        if not v or v.get('owner_id')!=uid or v.get('deleted'):raise WorkflowError('작업을 찾을 수 없습니다.',404)
        return v,gen
    def inputs(self,uid,task):
        v,_=self.load(uid,task);prefix=self.prefix(uid,task)
        raw=self.objects.read(prefix+'source.csv')[0]
        if raw is None or sha(raw)!=v['source_sha256']:raise WorkflowError('원본 파일 무결성 검사를 통과하지 못했습니다.',409)
        rawref=self.objects.read(prefix+'reference.csv')[0]
        if rawref is not None and sha(rawref)!=v['reference_sha256']:raise WorkflowError('대상 참고 파일 무결성 오류',409)
        source=checked_csv(raw);targets=parse_targets(v['target_schema'])
        return source,targets,raw,rawref
    def _json(self,uid,task,name):return read_json(self.objects,self.prefix(uid,task)+name)[0]
    def create(self,owner,payload,nonce,*,stored_demo=False):
        uid=identifier(owner['uid'])
        if not isinstance(nonce,str) or not re.fullmatch(r'[a-f0-9]{32,64}',nonce):raise WorkflowError('유효한 생성 요청 식별자가 필요합니다.')
        if stored_demo:
            raw=(ROOT/'examples/review_source.csv').read_bytes();targets=default_targets();rawref=None
            name='합성 상품 CSV · 저장된 실제 추천';filename='배포검증_합성상품.csv';reference_name=None
        else:
            try:
                if len(encode(payload.get('target_schema')))>65536:raise ValueError('대상 스키마는64KB 이하입니다.')
                raw=base64.b64decode(payload['source_b64'],validate=True)
                rawref=base64.b64decode(payload['reference_b64'],validate=True) if payload.get('reference_b64') is not None else None
                targets=parse_targets(payload['target_schema'])
            except (ValueError,KeyError,TypeError) as e:raise WorkflowError('CSV 또는 대상 스키마 입력이 올바르지 않습니다. '+str(e)[:160])
            name=payload.get('name','새 CSV 연결');filename=payload.get('source_name','source.csv');reference_name=payload.get('reference_name')
        if not isinstance(name,str) or not 1<=len(name.strip())<=100:raise WorkflowError('작업명은1~100자입니다.')
        if not isinstance(filename,str) or len(filename)>200:raise WorkflowError('파일 이름은200자 이하입니다.')
        source=checked_csv(raw);reference=checked_csv(rawref) if rawref is not None else None
        if {c.id for c in source.columns}&{t.id for t in targets}:raise WorkflowError('원본·대상 ID는 구분해야 합니다. 대상 ID를 t_ 등으로 지정하세요.')
        if reference_name is not None and (not isinstance(reference_name,str) or len(reference_name)>200):raise WorkflowError('대상 참고 파일 이름은200자 이하입니다.')
        if reference is not None and not {t.name for t in targets}<=set(reference.frame.columns):raise WorkflowError('대상 참고 CSV에는 정의한 모든 대상 열이 있어야 합니다.')
        wire=evidence(source,[Column(**t.model_dump(exclude={'required'})) for t in targets],reference)
        input_hash=digest([sha(raw),[t.model_dump() for t in targets],sha(rawref) if rawref is not None else None,name,filename])
        task=digest(['review-v2',uid,nonce])[:32];key=self.state_key(uid,task)
        existing,_=read_json(self.objects,key)
        if existing:
            if existing.get('deleted'):raise WorkflowError('삭제한 작업입니다. 새로운 요청 ID로 새 작업을 만들어 주세요.',409)
            if existing['input_hash']!=input_hash:raise WorkflowError('같은 요청 ID를 다른 입력에 재사용할 수 없습니다.',409)
            return self.public(uid,task)
        # Bound public demo storage without altering the model's20/day limit.
        own=self.objects.keys(f'review-v2/users/{uid}/tasks/')
        if sum(k.endswith('/state.json') for k in own)>=30:raise WorkflowError('시연 계정은 최대30작업을 보관합니다. 기존 작업을 정리해 주세요.',429)
        v={'task_id':task,'owner_id':uid,'name':name.strip(),'source_name':filename,'reference_name':reference_name,
            'source_sha256':sha(raw),'reference_sha256':sha(rawref) if rawref is not None else None,
            'target_schema':[t.model_dump() for t in targets],'target_schema_sha256':digest([t.model_dump() for t in targets]),
            'wire_sha256':digest(wire),'input_hash':input_hash,'created_at':now_iso(),'updated_at':now_iso(),
            'version':1,'rules_version':0,'phase':'draft','inference_state':'not_started','active_approval':None,
            'execution_count':0,'row_count':len(source.frame),'column_count':len(source.columns),
            'rules':[Rule(source_id=c.id,target_id=None).model_dump() for c in source.columns],
            'initial_result':None,'synthetic_demo':stored_demo}
        prefix=self.prefix(uid,task)
        immutable(self.objects,prefix+'source.csv',raw)
        if rawref is not None:immutable(self.objects,prefix+'reference.csv',rawref)
        immutable(self.objects,prefix+'wire.json',wire)
        if stored_demo:
            fixture=json.loads((ROOT/'examples/review_stored.json').read_bytes())
            if fixture['source_sha256']!=sha(raw) or fixture['wire_sha256']!=digest(wire):raise WorkflowError('저장된 시연 추천과 현재 입력이 일치하지 않습니다.',409)
            validate_recommendations([Recommendation.model_validate(x) for x in fixture['initial_recommendations']],source.columns,targets)
            result={'status':'success','request_id':'stored-'+digest(fixture)[:24],**fixture,'saved_at':fixture['saved_at'],'physical_POST_attempts':0,
                'provenance':'stored_actual_synthetic_C','new_inference_count':0}
            immutable(self.objects,prefix+'initial.json',result);self._attach(v,result)
        try:self.objects.write(key,v,0)
        except Conflict:
            existing,_=self.load(uid,task)
            if existing['input_hash']!=input_hash:raise WorkflowError('중복 생성 입력이 달라졌습니다.',409)
        return self.public(uid,task)
    def _attach(self,v,r):
        v['initial_result']={k:r.get(k) for k in ['request_id','saved_at','model_id','method','status','usage','usage_coverage','cost','error','physical_POST_attempts','model_call_seconds','wall_seconds','provenance','children']}
        uncertain=r.get('status')=='uncertain' or any(c.get('status')=='uncertain' for c in r.get('child_requests',[]))
        v['inference_state']='uncertain' if uncertain else 'completed' if r.get('status')=='success' else 'failed'
        initial={r['source_id']:r for r in r.get('initial_recommendations',[])}
        for rule in v['rules']:
            item=initial.get(rule['source_id']);rule['target_id']=item.get('target_id') if item else None
            rule['review_state']='unreviewed';rule['manual_resolution']=False;rule['transform_id']='identity'
        v['phase']='review';v['rules_version']+=1
    def public(self,uid,task):
        v,_=self.load(uid,task);source,targets,_,_=self.inputs(uid,task)
        result=self._json(uid,task,'initial.json');initial={r['source_id']:r for r in (result or {}).get('initial_recommendations',[])}
        cols=[];counts=Counter()
        for col in source.columns:
            item=initial.get(col.id)
            state=item['status'] if item else 'api_failure' if v['inference_state'] in ('failed','uncertain') else 'unprocessed'
            counts[state]+=1;values=list(dict.fromkeys(x for x in source.frame[col.name].tolist() if x!=''))[:3]
            cols.append({**col.model_dump(),'examples':[x[:80] for x in values],
                'initial':deepcopy(item) if item else {'source_id':col.id,'target_id':None,'status':state,'reason':None}})
        out={k:deepcopy(value) for k,value in v.items() if k not in ('input_hash',)}
        reference=checked_csv(self.objects.read(self.prefix(uid,task)+'reference.csv')[0]) if v.get('reference_sha256') else None
        assessments=connections(source,targets,[Rule.model_validate(x) for x in v['rules']],initial,reference)
        out.update(connections=assessments,connection_assessment_version=ASSESSMENT_VERSION,
            columns=cols,counts={k:counts[k] for k in ['matched','needs_review','no_match','api_failure','unprocessed']},
            profile=self._json(uid,task,'wire.json'),unlinked_policy='연결하지 않은 원본 열은 unmapped.csv에 값 그대로 별도 보존합니다.')
        return out
    def list(self,uid):
        out=[]
        for k in self.objects.keys(f'review-v2/users/{identifier(uid)}/tasks/'):
            if k.endswith('/state.json'):
                v,_=read_json(self.objects,k)
                if v and not v.get('deleted') and v['owner_id']==uid:out.append({key:v[key] for key in ['task_id','name','source_name','phase','created_at','row_count','column_count','version','inference_state']})
        return sorted(out,key=lambda t:t['created_at'],reverse=True)
    def recommend(self,owner,task,expected_version):
        uid=owner['uid'];v,gen=self.load(uid,task)
        if v['initial_result'] is not None:return self.public(uid,task),True
        if v['inference_state']=='running':raise WorkflowError('기존 추천 요청이 진행 중이거나 완료 미확정입니다. 재호출하지 않고 상태를 조회하세요.',409)
        if v['version']!=expected_version:raise WorkflowError('다른 창에서 작업이 변경됐습니다. 새로고침 후 확인해 주세요.',409)
        v.update(inference_state='running',phase='inferencing',version=v['version']+1,updated_at=now_iso())
        self.objects.write(self.state_key(uid,task),v,gen)
        source,targets,raw,rawref=self.inputs(uid,task);wire=self._json(uid,task,'wire.json');store=InferenceStore(self.objects,uid,task)
        try:
            result,_=self.infer(store,wire,raw,rawref)
        except Exception as e:
            result={'request_id':uuid.uuid4().hex,'status':'failed','saved_at':now_iso(),'model_id':load_config()['model'],
                'method':'C','initial_recommendations':[],'error':'추천 요청 실패: '+type(e).__name__,'physical_POST_attempts':0}
        immutable(self.objects,self.prefix(uid,task)+'initial.json',result)
        current,gen=self.load(uid,task);self._attach(current,result)
        current.update(version=current['version']+1,updated_at=now_iso())
        self.objects.write(self.state_key(uid,task),current,gen)
        return self.public(uid,task),False
    def recover(self,uid,task):
        v,gen=self.load(uid,task)
        if v['inference_state']!='running':return self.public(uid,task)
        source,targets,raw,rawref=self.inputs(uid,task);wire=self._json(uid,task,'wire.json')
        result=load_saved(InferenceStore(self.objects,uid,task),file_fingerprint(wire,raw,rawref))
        if not result:raise WorkflowError('아직 완료 응답이 없습니다. 새 추론 없이 같은 작업을 나중에 다시 조회하세요.',202)
        immutable(self.objects,self.prefix(uid,task)+'initial.json',result);self._attach(v,result)
        v.update(version=v['version']+1,updated_at=now_iso());self.objects.write(self.state_key(uid,task),v,gen)
        return self.public(uid,task)
    def save_rules(self,uid,task,version,values):
        v,gen=self.load(uid,task)
        if v['phase'] in ('executing','inferencing'):raise WorkflowError('실행 중에는 규칙을 바꿀 수 없습니다.',423)
        if v['version']!=version:raise WorkflowError('저장 버전이 달라졌습니다. 새로고침 후 다시 확인하세요.',409)
        try:rules=[Rule.model_validate(x) for x in values]
        except (ValueError,TypeError):raise WorkflowError('검토 규칙 형식이 올바르지 않습니다.')
        source,targets,_,_=self.inputs(uid,task)
        if len(rules)!=len(source.columns) or {r.source_id for r in rules}!={c.id for c in source.columns}:raise WorkflowError('모든 원본 항목의 규칙이 필요합니다.')
        if any(r.target_id is not None and r.target_id not in {t.id for t in targets} for r in rules):raise WorkflowError('허용되지 않은 대상 ID입니다.')
        by_id={r.source_id:r for r in rules}
        serialized=[by_id[c.id].model_dump() for c in source.columns]
        if serialized==v['rules']:return self.public(uid,task)
        v.update(rules=serialized,rules_version=v['rules_version']+1,version=v['version']+1,
            active_approval=None,phase='review',updated_at=now_iso())
        self.objects.write(self.state_key(uid,task),v,gen)
        return self.public(uid,task)
    def rule_hash(self,v):return digest({'version':VERSION,'source':v['source_sha256'],'schema':v['target_schema_sha256'],
        'reference':v['reference_sha256'],'rules_version':v['rules_version'],'rules':v['rules']})
    def validation(self,uid,task,require_review=True):
        v,_=self.load(uid,task);source,targets,_,_=self.inputs(uid,task)
        result=self._json(uid,task,'initial.json');initial={r['source_id']:r for r in (result or {}).get('initial_recommendations',[])}
        out=evaluate(source,targets,[Rule.model_validate(x) for x in v['rules']],initial,require_review=require_review)
        reference=checked_csv(self.objects.read(self.prefix(uid,task)+'reference.csv')[0]) if v.get('reference_sha256') else None
        out['connections']=connections(source,targets,[Rule.model_validate(x) for x in v['rules']],initial,reference)
        for item in out['connections']:
            if item['semantic']['user_selected_target_id'] and item['conversion']['status'] in ('blocked','rule_required'):
                out['issues'].append({'code':'conversion_unresolved','source_id':item['source_id'],'message':item['conversion']['reason']})
        if v['inference_state'] in ('running','uncertain'):out['issues'].append({'code':'inference_pending','message':'완료 여부 미확정 추천이 있어 승인을 차단합니다. 기존 ID부터 회수하세요.'})
        return out
    def preview(self,uid,task):
        v,_=self.load(uid,task);ev=self.validation(uid,task);rule_hash=self.rule_hash(v)
        if ev['row_errors']:
            errors=csvbytes(['row_number','source_name','target_name','reason'],[[r[k] for k in ['row_number','source_name','target_name','reason']] for r in ev['row_errors']])
            immutable(self.objects,self.prefix(uid,task)+f'validation/{rule_hash}.csv',errors)
        return {'version':v['version'],'rules_version':v['rules_version'],'rule_hash':rule_hash,
            'issues':ev['issues'],'connections':ev['connections'],'row_errors':ev['row_errors'][:100],'total_row_errors':len(ev['row_errors']),
            'all_rows_checked':ev.get('all_rows_checked',v['row_count']),'no_rows_dropped':True,'headers':ev['headers'],'rows':ev['rows'][:20],
            'preview_limit':20,'can_approve':not ev['issues'] and not ev['row_errors'],
            'unlinked_policy':'미연결 열은 unmapped.csv로 별도 보존','row_number_basis':ev.get('row_number_basis')}
    def approve(self,owner,task,version,expected_hash):
        uid=owner['uid'];v,gen=self.load(uid,task);current_hash=self.rule_hash(v)
        if current_hash!=expected_hash:raise WorkflowError('미리보기 이후 규칙이 바뀌었습니다. 다시 확인해 주세요.',409)
        if v['active_approval'] and v['active_approval'].get('rule_hash')==current_hash:
            ev=self.validation(uid,task)
            if ev['issues'] or ev['row_errors']:raise WorkflowError('현재 변환 검사를 통과하지 못했습니다.',422,{'issues':ev['issues']})
            return self.public(uid,task),True
        if v['phase'] in ('executing','inferencing'):raise WorkflowError('기존 실행의 완료 상태를 먼저 확인해 주세요.',409)
        if version!=v['version']:raise WorkflowError('작업 버전이 변경됐습니다. 다시 미리보기해 주세요.',409)
        ev=self.validation(uid,task)
        if ev['issues'] or ev['row_errors']:raise WorkflowError('승인 전 해결할 항목이 있습니다.',422,{'issues':ev['issues'],'row_errors':ev['row_errors'][:100],'total_row_errors':len(ev['row_errors'])})
        source,targets,_,_=self.inputs(uid,task);aid=digest([uid,task,current_hash,VERSION])[:32]
        approval={'approval_id':aid,'rule_hash':current_hash,'rules_version':v['rules_version'],'rules':deepcopy(v['rules']),
            'approved_at':now_iso(),'approved_by':uid,'approved_username':owner['username'],'authentication':owner['authentication'],
            'source_sha256':v['source_sha256'],'source_name':v['source_name'],'target_schema_sha256':v['target_schema_sha256'],
            'reference_sha256':v['reference_sha256'],'engine_config_sha256':digest(load_config()),'transform_version':VERSION,
            'connection_assessment_version':ASSESSMENT_VERSION,'connections':ev['connections'],'execution_id':aid,'status':'running'}
        v.update(phase='executing',active_approval=approval,version=v['version']+1,execution_count=v['execution_count']+1,updated_at=now_iso())
        # Exactly one contender obtains the generation; losers never execute.
        try:claimed=self.objects.write(self.state_key(uid,task),v,gen)
        except Conflict:return self.public(uid,task),True
        prefix=self.prefix(uid,task);immutable(self.objects,prefix+f'approvals/{aid}/approval.json',approval)
        try:
            files=self.executor(source,targets,[Rule.model_validate(x) for x in v['rules']],ev)
            finished_at=now_iso()
            csv_locations={name:prefix+f'approvals/{aid}/files/'+name for name in files}
            files['rules.json']=encode({**approval,'status':'completed','finished_at':finished_at,
                'row_count':len(source.frame),'result_files':csv_locations,'no_rows_dropped':True})
            paths={};hashes={}
            for name,raw in files.items():
                path=prefix+f'approvals/{aid}/files/'+name;immutable(self.objects,path,raw);paths[name]=path;hashes[name]=sha(raw)
            execution={'approval_id':aid,'rule_hash':current_hash,'execution_id':aid,'status':'completed','finished_at':finished_at,
                'row_count':len(source.frame),'result_files':paths,'file_sha256':hashes,'no_rows_dropped':True}
            immutable(self.objects,prefix+f'approvals/{aid}/execution.json',execution)
            v['active_approval']={**approval,**execution};v.update(phase='completed',version=v['version']+1,updated_at=now_iso())
            self.objects.write(self.state_key(uid,task),v,claimed)
        except Exception as e:
            # A partial execution is never automatically replayed. Inputs/receipt
            # and any already-written immutable files remain for reconciliation.
            current,generation=self.load(uid,task);current['phase']='execution_failed';current['active_approval']['status']='failed'
            current['active_approval']['error']='결과 저장 실패: '+type(e).__name__;current['version']+=1
            self.objects.write(self.state_key(uid,task),current,generation)
            raise WorkflowError('결과 생성·저장이 완료되지 않았습니다. 같은 실행 ID를 확인해야 합니다.',500)
        return self.public(uid,task),False
    def download(self,uid,task,approval_id,filename):
        v,_=self.load(uid,task);a=v.get('active_approval')
        if not a or a['approval_id']!=approval_id or a['status']!='completed' or a['rule_hash']!=self.rule_hash(v):raise WorkflowError('현재 규칙에 대해 최종 승인·생성이 완료된 파일만 다운로드할 수 있습니다.',409)
        ev=self.validation(uid,task)
        if ev['issues'] or ev['row_errors']:raise WorkflowError('현재 의미 연결·변환 검사를 통과하지 못했습니다. 다시 검토하세요.',409)
        if filename not in a['result_files']:raise WorkflowError('파일을 찾을 수 없습니다.',404)
        raw=self.objects.read(a['result_files'][filename])[0]
        if raw is None or sha(raw)!=a['file_sha256'][filename]:raise WorkflowError('파일 보관기간이 만료됐거나 무결성이 일치하지 않습니다.',409)
        return raw
    def errors_file(self,uid,task):
        v,_=self.load(uid,task);raw=self.objects.read(self.prefix(uid,task)+f'validation/{self.rule_hash(v)}.csv')[0]
        if raw is None:raise WorkflowError('현재 규칙의 오류 목록이 없습니다. 미리보기부터 실행해 주세요.',404)
        return raw
    def delete(self,uid,task):
        v,gen=self.load(uid,task)
        if v['phase'] in ('inferencing','executing'):raise WorkflowError('진행 중인 작업은 완료 상태부터 확인해 주세요.',409)
        tombstone={'task_id':task,'owner_id':uid,'deleted':True,'version':v['version']+1,'deleted_at':now_iso()}
        self.objects.write(self.state_key(uid,task),tombstone,gen)
        for prefix in [self.prefix(uid,task),InferenceStore(self.objects,uid,task).prefix]:
            for key in self.objects.keys(prefix):
                if key==self.state_key(uid,task):continue
                _,generation=self.objects.read(key)
                if generation:self.objects.delete(key,generation)
        return {'deleted':True,'task_id':task}
