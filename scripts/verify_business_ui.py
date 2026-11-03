"""Local presentation fixtures, not model results or research evaluation.

Real saved synthetic recommendations seed the layout. Long names, failure
states and a stalled/failed preview are mocked only in this isolated browser.
No recommendation request is permitted; no fixture changes server records.
"""
import argparse, json, secrets, uuid
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect

p=argparse.ArgumentParser()
p.add_argument('--out',default='deployment-artifacts/business-ui/presentation')
a=p.parse_args(); out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
base='http://127.0.0.1:8504'; checks=[];errors=[];blocked=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True)
    context=browser.new_context(viewport={'width':1600,'height':1050})
    def guard(route):
        req=route.request; host=urlsplit(req.url).netloc
        if host not in {'127.0.0.1:8504','fonts.googleapis.com','fonts.gstatic.com'} or req.url.endswith('/recommend'):
            blocked.append(req.url.split('?')[0]);route.abort();return
        route.continue_()
    context.route('**/*',guard)
    r=context.request.post(base+'/api/register',data={'username':'layout-'+uuid.uuid4().hex[:12],'password':secrets.token_urlsafe(30)})
    assert r.status==201
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base,wait_until='networkidle')
    page.get_by_role('button',name='저장된 합성 예제 열기',exact=True).click()
    expect(page.get_by_role('heading',name='연결 결과 검토',exact=True)).to_be_visible()
    original=page.evaluate('JSON.parse(JSON.stringify(S.task))')
    table_top=page.locator('.review-table').bounding_box()['y']
    assert table_top<500,table_top
    for width in [1600,1366]:
        page.set_viewport_size({'width':width,'height':1050})
        assert page.evaluate('document.documentElement.scrollWidth')<=width
        assert page.locator('#review-scroll').evaluate('(e)=>e.scrollWidth<=e.clientWidth+2')
    checks.append('desktop_table_above_500px_and_no_horizontal_scroll_1366_1600')
    page.set_viewport_size({'width':1600,'height':1050})
    page.evaluate('''(original)=>{
      const t=JSON.parse(JSON.stringify(original));t.name='모의 화면 검증: 긴 항목명·실패·검토 상태';
      const statuses=['needs_review','no_match','api_failure','unprocessed'];
      t.columns=statuses.map((status,i)=>({...t.columns[i%2],id:'src_'+i,name:i===0?'거래처에서_전달한_외부_상품_식별코드_및_관리번호_'.repeat(4):['','대응하지_않는_메모','추천_실패_항목','미처리_항목'][i],initial:{source_id:'src_'+i,status,target_id:null,reason:i<2?'모의 표시 검증용 근거입니다. 실제 모델 응답이 아닙니다.':null}}));
      t.rules=t.columns.map(c=>({source_id:c.id,target_id:null,transform_id:'identity',review_state:'unreviewed',manual_resolution:false}));
      t.column_count=4;t.counts={matched:0,needs_review:1,no_match:1,api_failure:1,unprocessed:1};
      t.initial_result.status='failed';t.inference_state='failed';
      t.target_schema[0].name='external_product_identifier_'.repeat(7);
      setTask(t);
    }''',original)
    for index,text in [(0,'대상 판단 보류'),(1,'연결 대상 없음'),(2,'추천 결과 없음'),(3,'아직 추천하지 않음')]:
        expect(page.locator(f'tr[data-row="{index}"]').get_by_text(text,exact=True)).to_be_visible()
    checks.append('mock_review_no_match_api_failure_unprocessed_are_distinct')
    strong=page.locator('tr[data-row="0"] .source-cell strong')
    assert strong.evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
    assert strong.bounding_box()['height']>40
    page.screenshot(path=str(out/'long-names-and-states.png'),full_page=True)
    checks.append('long_names_wrap_without_overlap')
    page.get_by_label('항목명 검색',exact=True).fill('해당없음-검색검증')
    expect(page.locator('#no-columns')).to_be_visible()
    page.get_by_label('항목명 검색',exact=True).fill('')
    checks.append('empty_search_explains_next_action')
    scroll=page.locator('#review-scroll');scroll.evaluate('(e)=>e.scrollTop=100')
    assert abs(page.locator('.review-table th').first.bounding_box()['y']-scroll.bounding_box()['y'])<3
    checks.append('table_header_stays_visible')
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth')<=390
    scroll.evaluate('(e)=>e.scrollLeft=320')
    page.locator('[data-rule="target_id"][data-index="0"]').focus()
    page.locator('[data-rule="target_id"][data-index="0"]').select_option('product_code')
    assert page.locator('#review-scroll').evaluate('(e)=>e.scrollLeft')>=319
    assert page.evaluate('document.activeElement.dataset.rule')=='target_id'
    expect(page.locator('#save-indicator')).to_contain_text('저장하지 않은 변경')
    page.locator('[data-rule="transform_id"][data-index="0"]').select_option('unsupported')
    expect(page.locator('#approval-issues')).to_contain_text('지원하지 않는 변환')
    approve=page.get_by_role('button',name='승인 후 결과 생성',exact=True)
    approve.scroll_into_view_if_needed();expect(approve).to_be_in_viewport()
    page.screenshot(path=str(out/'mobile-approval-errors.png'),full_page=True)
    checks.append('mobile_scroll_edit_focus_unsaved_state_and_approval_reachable')
    page.evaluate('setTask',original)
    pending=[]
    page.route('**/preview',lambda r:pending.append(r))
    page.get_by_role('button',name='결과 미리보기',exact=True).click()
    expect(page.locator('#busy-indicator')).to_be_visible()
    expect(page.get_by_role('button',name='승인 후 결과 생성',exact=True)).to_be_disabled()
    assert pending
    pending.pop().fulfill(status=422,json={'error':'모의 오류: 날짜 형식을 확인하세요.'})
    expect(page.locator('#action-error')).to_contain_text('날짜 형식을 확인하세요')
    expect(page.locator('#busy-indicator')).to_be_hidden()
    expect(page.get_by_role('heading',name='결과 CSV 생성 완료',exact=True)).to_have_count(0)
    checks.append('pending_feedback_and_persistent_failure_without_false_success')
    assert not errors and not blocked,(errors,blocked)
    report={'checks':checks,'table_top_px':table_top,'page_errors':errors,'new_model_calls':0,
            'presentation_states_mocked':True,'not_model_predictions_or_accuracy':True,'reference_site_interactions':0}
    (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,indent=2));browser.close()
