"""Isolated software-test browser, never the user's native browser session.

Only this owned app's allowlisted origins are navigated. Reference site is never
visited or modified. Recommendation POST is blocked: this script generates0.
"""
import argparse,csv,io,json,re,secrets,sys,uuid
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect

ALLOWED={'http://127.0.0.1:8504','https://schema-c-web-392692577987.asia-northeast3.run.app',
    'https://schema-c-web-42mhsk5ogq-du.a.run.app'}
p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8504');p.add_argument('--out',default='deployment-artifacts/review-web-v2/local-ui');a=p.parse_args()
base=a.base.rstrip('/')
if base not in ALLOWED:raise SystemExit('Only the owned local/Cloud Run schema app is permitted')
out=Path(a.out);out.mkdir(parents=True,exist_ok=True);checks=[];errors=[];blocked=[]
username='ui-'+uuid.uuid4().hex[:14];password=secrets.token_urlsafe(30)
def origin(url):v=urlsplit(url);return f'{v.scheme}://{v.netloc}'

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True)
    context=browser.new_context(viewport={'width':1600,'height':1050},accept_downloads=True)
    def route(r):
        u=r.request.url
        if origin(u) not in (base,'https://fonts.googleapis.com','https://fonts.gstatic.com') or u.endswith('/recommend'):
            blocked.append(u.split('?')[0]);r.abort();return
        r.continue_()
    context.route('**/*',route)
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    r=context.request.post(base+'/api/register',data={'username':username,'password':password})
    assert r.status==201,r.status;user=r.json();csrf=user['csrf']
    page.goto(base,wait_until='networkidle');expect(page.get_by_role('heading',name='오늘의 데이터 연결',exact=True)).to_be_visible()
    page.screenshot(path=str(out/'home.png'),full_page=True);checks.append('authenticated_home')
    page.get_by_role('button',name='저장된 합성 시연 열기',exact=True).click()
    expect(page.get_by_role('heading',name='연결 결과 검토',exact=True)).to_be_visible()
    expect(page.get_by_text('저장된 실제 추천 · 합성 시연',exact=True)).to_be_visible();checks.append('real_cached_recommendations_labeled')
    page.screenshot(path=str(out/'review-desktop.png'),full_page=True)
    page.get_by_role('button',name=re.compile('^데이터 특징 확인')).click()
    expect(page.get_by_role('columnheader',name='결측률',exact=True)).to_be_visible()
    expect(page.get_by_role('heading',name='대상 표준 정의',exact=True)).to_be_visible()
    page.get_by_role('button',name='닫기',exact=True).click();checks.append('readable_both_side_profiles_and_schema')
    page.get_by_role('button',name='최종 승인 및 결과 생성',exact=True).click()
    expect(page.get_by_role('dialog').get_by_text('아직 승인할 수 없습니다.',exact=False)).to_be_visible();checks.append('unreviewed_approval_blocked')
    page.get_by_role('button',name='닫기',exact=True).click()
    page.get_by_label('상품코드 최종 대상',exact=True).select_option('product_name')
    page.get_by_role('button',name='현재 연결 모두 확인',exact=True).click()
    page.get_by_role('button',name='최종 승인 및 결과 생성',exact=True).click()
    expect(page.get_by_role('dialog').get_by_text(re.compile('중복 연결'))).to_be_visible();checks.append('duplicate_and_required_target_blocked')
    page.get_by_role('button',name='닫기',exact=True).click()
    page.get_by_role('button',name='AI 추천으로 되돌리기',exact=True).last.click()
    page.get_by_role('button',name='현재 연결 모두 확인',exact=True).click()
    page.get_by_label('항목명 검색',exact=True).fill('상품코드')
    assert page.locator('tr[data-row="1"]').is_hidden();checks.append('column_search')
    page.get_by_label('항목명 검색',exact=True).fill('')
    page.get_by_role('button',name='결과 미리보기',exact=True).click()
    expect(page.get_by_role('dialog').get_by_text('00124',exact=True)).to_be_visible();checks.append('preview_original_values')
    page.screenshot(path=str(out/'preview.png'),full_page=True)
    page.get_by_role('button',name='닫기',exact=True).click()
    page.get_by_role('button',name='최종 승인 및 결과 생성',exact=True).click()
    expect(page.get_by_role('heading',name='승인된 규칙으로 결과 생성 완료',exact=True)).to_be_visible();checks.append('approval_executes_results')
    with page.expect_download() as dl:page.get_by_role('link',name='결과 CSV 다운로드',exact=True).click()
    dl.value.save_as(out/'standardized.csv')
    rows=list(csv.reader(io.StringIO((out/'standardized.csv').read_text('utf-8-sig'))))
    original=list(csv.reader(io.StringIO((Path(__file__).resolve().parents[1]/'examples/review_source.csv').read_text('utf-8-sig'))))
    assert rows==[['product_code','product_name'],*original[1:]],'Downloaded data differs from the real cached synthetic source'
    with page.expect_download() as dl:page.get_by_role('link',name='연결표 다운로드',exact=True).click()
    dl.value.save_as(out/'mapping.csv');checks.append('download_values_and_mapping')
    task_id=urlsplit(page.url).query.split('task=')[1];state=context.request.get(base+'/api/tasks/'+task_id).json()
    assert state['execution_count']==1 and state['initial_result']['physical_POST_attempts']==0
    approval=state['active_approval'];before=state['execution_count']
    rulefile=context.request.get(f'{base}/api/tasks/{task_id}/files/{approval["approval_id"]}/rules.json').json()
    assert rulefile['status']=='completed' and 'standardized.csv' in rulefile['result_files']
    retry=context.request.post(base+'/api/tasks/'+task_id+'/approve',headers={'X-CSRF-Token':csrf},data={'version':state['version'],'rule_hash':approval['rule_hash']})
    assert retry.status==200 and retry.json()['reused'] and retry.json()['task']['execution_count']==before;checks.append('duplicate_approval_no_execution')
    page.reload(wait_until='networkidle');expect(page.get_by_role('link',name='결과 CSV 다운로드',exact=True)).to_be_visible();checks.append('refresh_reopens_without_inference')
    page.screenshot(path=str(out/'approved.png'),full_page=True)
    page.get_by_label('ITEM_NM 최종 대상',exact=True).select_option('')
    assert page.get_by_role('link',name='결과 CSV 다운로드',exact=True).count()==0
    page.get_by_role('button',name='검토 내용 저장',exact=True).click()
    expect(page.get_by_text(re.compile('저장됨 · 규칙 v'))).to_be_visible()
    old=context.request.get(f'{base}/api/tasks/{task_id}/files/{approval["approval_id"]}/standardized.csv')
    assert old.status==409;checks.append('edit_revokes_approval_and_download')
    page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(out/'review-mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth')<=390;checks.append('mobile_no_page_overflow')
    page.set_viewport_size({'width':1600,'height':1050})
    page.get_by_role('button',name='새 CSV 연결',exact=True).click()
    page.locator('#source-file').set_input_files(str(Path(__file__).resolve().parents[1]/'examples/review_source.csv'))
    cfg=context.request.get(base+'/api/config').json()
    (out/'target-schema.json').write_text(json.dumps({'fields':cfg['targets']},ensure_ascii=False),encoding='utf8')
    (out/'reference.csv').write_text('product_code,product_name,quantity,unit_price,total_amount,order_date\n00124,무선 마우스,2,12000,24000,2026-11-03\n00007,유선 키보드,1,15000,15000,2026-11-03\n',encoding='utf-8-sig')
    page.locator('#schema-file').set_input_files(str((out/'target-schema.json').resolve()))
    page.locator('#reference-file').set_input_files(str((out/'reference.csv').resolve()))
    page.get_by_role('button',name=re.compile('^파일 등록 및 특징 확인')).click()
    expect(page.get_by_role('button',name='Gemini C 추천 실행',exact=True)).to_be_visible()
    expect(page.get_by_text('6/6항목 제공',exact=True)).to_be_visible();checks.append('source_upload_custom_schema_and_reference_csv_no_inference')
    page.screenshot(path=str(out/'uploaded-ready.png'),full_page=True)
    other=browser.new_context();r=other.request.post(base+'/api/register',data={'username':'ui-'+uuid.uuid4().hex[:14],'password':secrets.token_urlsafe(30)});assert r.status==201
    assert other.request.get(base+'/api/tasks/'+task_id).status==404;checks.append('other_user_task_id_denied')
    assert not errors,errors
    assert not [u for u in blocked if u.endswith('/recommend')],blocked
    summary={'base':base,'checks':checks,'page_errors':errors,'new_model_calls':0,'recommendation_requests':0,
        'task_id':task_id,'reference_site_interactions':0,'isolated_test_browser':True,'passwords_or_session_tokens_in_report':False}
    (out/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False,indent=2));browser.close()
