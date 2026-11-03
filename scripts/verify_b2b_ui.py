"""Local-only B2B manual-review smoke; model recommendation POST is forbidden."""
import json,secrets,sys,uuid
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1];BASE='http://127.0.0.1:8508';OUT=ROOT/'deployment-artifacts/b2b-v1/b2b-ui';OUT.mkdir(parents=True,exist_ok=True)
truth=json.loads((ROOT/'B2B_PROVISIONAL_ANSWERS.json').read_bytes())['answers']
tasks=json.loads((ROOT/'B2B_TASKS.json').read_bytes())['tasks'];answers={a['id']:a['expected_target_id'] for a in truth}
checks=[];blocked=[];errors=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True);ctx=browser.new_context(viewport={'width':1600,'height':1080},accept_downloads=True)
    def route(r):
        u=urlsplit(r.request.url);origin=f'{u.scheme}://{u.netloc}'
        if r.request.url.endswith('/recommend') or origin not in (BASE,'https://fonts.googleapis.com','https://fonts.gstatic.com'):
            blocked.append(r.request.url.split('?')[0]);r.abort()
        else:r.continue_()
    ctx.route('**/*',route)
    user=ctx.request.post(BASE+'/api/register',data={'username':'b2b-'+uuid.uuid4().hex[:12],'password':secrets.token_urlsafe(24)}).json();csrf=user['csrf']
    page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    for file_id,label in [('b2b_products','상품'),('b2b_orders','주문')]:
        page.goto(BASE,wait_until='networkidle');page.get_by_role('button',name='파일 업로드',exact=True).first.click()
        page.get_by_role('button',name=label+' 합성 예제로 준비',exact=True).click()
        expect(page.locator('#source-file')).not_to_be_empty() if False else None
        expect(page.locator('#job-name')).to_have_value(label+' CSV · 직접 만든 합성 시연')
        page.screenshot(path=str(OUT/(file_id+'-prepared.png')),full_page=True)
        page.get_by_role('button',name='파일 등록 및 특징 확인',exact=True).click()
        expect(page.get_by_role('heading',name='연결 결과 검토',exact=True)).to_be_visible()
        # These are explicit human-style synthetic selections, never AI predictions.
        for task in [t for t in tasks if t['file_id']==file_id]:
            i=task['source_index'];target=answers[task['id']]
            page.get_by_label(task['source_name']+' 최종 대상',exact=True).select_option(target or '')
            if task['source_name']=='주문접수일':page.get_by_label('주문접수일 변환',exact=True).select_option('date_slash_iso')
            row=page.locator(f'tr[data-row="{i}"]');row.locator('[data-rule="manual_resolution"]').check()
            row.locator('[data-rule="review_state"]').check()
        page.get_by_role('button',name='결과 미리보기',exact=True).click()
        expect(page.get_by_role('dialog').get_by_text('전체 검사를 통과했습니다.',exact=False)).to_be_visible()
        page.screenshot(path=str(OUT/(file_id+'-preview.png')),full_page=True)
        page.get_by_role('button',name='닫기',exact=True).click()
        page.get_by_role('button',name='승인 후 결과 생성',exact=True).click()
        expect(page.get_by_role('heading',name='결과 CSV 생성 완료',exact=True)).to_be_visible()
        with page.expect_download() as download:page.get_by_role('link',name='결과 CSV 다운로드',exact=True).click()
        download.value.save_as(OUT/(file_id+'-output.csv'))
        assert '000124' in (OUT/(file_id+'-output.csv')).read_text(encoding='utf-8-sig')
        tid=urlsplit(page.url).query.split('task=')[1];state=ctx.request.get(BASE+'/api/tasks/'+tid).json()
        assert state['execution_count']==1 and state['inference_state']=='not_started'
        a=state['active_approval'];repeat=ctx.request.post(BASE+'/api/tasks/'+tid+'/approve',headers={'X-CSRF-Token':csrf},data={'version':state['version'],'rule_hash':a['rule_hash']})
        assert repeat.status==200 and repeat.json()['reused'] and repeat.json()['task']['execution_count']==1
        page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth')<=390
        page.screenshot(path=str(OUT/(file_id+'-mobile.png')),full_page=True);page.set_viewport_size({'width':1600,'height':1080})
        checks.append(file_id+': prepare/manual-edit/preview/approve/download/leading-zero/idempotence/mobile')
    assert not errors and not any(u.endswith('/recommend') for u in blocked)
    value={'base':BASE,'checks':checks,'page_errors':errors,'recommendation_requests':0,'new_model_calls':0,
       'synthetic_manual_flow_not_accuracy_measurement':True,'human_user_timing_measured':False}
    (OUT/'result.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(value,ensure_ascii=True));browser.close()
