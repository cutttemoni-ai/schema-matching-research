"""Official file-download paths only; immutable raw bytes, no authentication bypass.

Portal standard CSV buttons serialize paginated JSON in the browser. We retain
those original JSON responses AND a reversible UTF-8 CSV serialization. This is
not the authenticated OpenAPI product. Real rows stay under ignored datasets/.
"""
import argparse,csv,hashlib,io,json,re,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'datasets/korea-v1'
URLS={'shops':'https://www.data.go.kr/data/15083033/fileData.do',
 'restaurants':'https://www.data.go.kr/data/15096283/standard.do',
 'markets':'https://www.data.go.kr/data/15012894/standard.do',
 'parking':'https://www.data.go.kr/data/15012896/standard.do'}
SEOU='https://data.seoul.go.kr/dataList/OA-23056/S/1/datasetView.do'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def save(p,b):
    p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():
        if p.read_bytes()!=b:raise ValueError('Immutable file changed: '+str(p))
    else:p.write_bytes(b)
def get(url,p,**kwargs):
    if p.exists():return p.read_bytes()
    r=requests.get(url,timeout=180,**kwargs);r.raise_for_status();save(p,r.content);return r.content
def csv_load(p,encoding=None):
    b=p.read_bytes()
    for enc in ([encoding] if encoding else ['utf-8-sig','cp949']):
        try:t=b.decode(enc);break
        except UnicodeDecodeError:continue
    else:raise ValueError('Unsupported encoding')
    rows=list(csv.reader(io.StringIO(t,newline=''),strict=True));heads=rows.pop(0)
    if len(set(heads))!=len(heads) or any(not h.strip() for h in heads):raise ValueError('Duplicate/empty header')
    if any(len(r)!=len(heads) for r in rows):raise ValueError('Ragged rows')
    return heads,rows,enc
def standard(name,pk):
    pages=OUT/'pages';raw=OUT/'raw';derived=OUT/'derived'
    h=json.loads(get('https://www.data.go.kr/download/columList.json',pages/f'{pk}-columns.json',params={'pk':pk,'ext':'CSV'}))
    allrows=[];parts=[]
    for page in range(1,(h['totalCount']+9999)//10000+1):
        qs=[('publicDataPk',pk),('totalCount',h['totalCount']),('svcTableNm',h['tableVO']['svcTableNm']),('perPage',10000),('page',page)]
        qs += [('colNmList',c) for c in h['tableVO']['colNmList']]
        p=pages/f'{name}-data-{page}.json';b=get('https://www.data.go.kr/download/standard.json',p,params=qs)
        save(raw/p.name,b);parts.append(p.name);allrows+=json.loads(b)
    cols=h['columList'];codes=[c['columCode'] for c in cols];heads=[c['columNm'] for c in cols]
    assert len(allrows)==h['totalCount'] and all(set(r)==set(codes) for r in allrows)
    assert all(v is None or isinstance(v,str) for row in allrows for v in row.values()),'Unexpected nonstring must not be coerced'
    text=io.StringIO(newline='');w=csv.writer(text);w.writerow(heads)
    w.writerows([[r[c] if r[c] is not None else '' for c in codes] for r in allrows])
    dest=derived/(name+'.csv');save(dest,text.getvalue().encode('utf-8-sig'))
    nulls=[(i,c) for i,r in enumerate(allrows) for c in codes if r[c] is None]
    save(derived/(name+'-json-null-mask.json'),json.dumps(nulls,ensure_ascii=False).encode('utf8'))
    return {'csv':str(dest.relative_to(ROOT)),'raw_parts':parts,'original_json_null_cells':len(nulls),
        'format':'official CSV-button JSON, lossless string CSV serialization; JSON null mask separate',
        'download_endpoint':'https://www.data.go.kr/download/standard.json','count_from_download':len(allrows)}
def acquire():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'acquisition.json').exists():
        previous=json.loads((OUT/'acquisition.json').read_bytes())
        for name,item in previous['files'].items():
            assert sha(ROOT/name)==item['sha256'], 'Preserved download changed: '+name
        print('Existing acquisition verified; no download or manifest overwrite')
        return previous
    for name,url in URLS.items():get(url,OUT/'pages'/f'{name}.html')
    # Discover current file ID from the official file detail response, not an invented URL.
    html=(OUT/'pages/shops.html').read_text('utf8');m=re.search(r"fn_fileDataDown\('15083033',\s*'([^']+)'",html)
    if not m:raise RuntimeError('Current official shops detail link changed')
    detail=OUT/'pages/shops-detail.html'
    if not detail.exists():
        r=requests.post('https://www.data.go.kr/tcs/dss/selectDpkDetailInfo.do',data={'publicDataDetailPk':m[1],'publicDataHistSn':1},timeout=60);r.raise_for_status();save(detail,r.content)
    text=detail.read_text('utf8');fid=re.search(r'FILE_\d+',text)[0]
    url='https://www.data.go.kr/cmm/cmm/fileDownload.do';zpath=OUT/'raw/shops-20260930.zip'
    cached=OUT/'pages/shops-zip-tail.bin'
    if not zpath.exists() and cached.exists() and zipfile.is_zipfile(cached):cached.rename(zpath)
    if not zpath.exists():
        check=requests.post('https://www.data.go.kr/cmm/cmm/check-limit.json',data={'atchFileId':fid,'fileDetailSn':1},timeout=60);check.raise_for_status()
        if check.json().get('needCaptcha'):raise RuntimeError('Portal CAPTCHA requires human action; no bypass')
        get(url,zpath,params={'atchFileId':fid,'fileDetailSn':1,'dataNm':'소상공인시장진흥공단_상가(상권)정보_20260930'})
    with zipfile.ZipFile(zpath) as z:
        inventory=[{'name':n.filename,'bytes':n.file_size,'compressed_bytes':n.compress_size,'crc32':n.CRC} for n in z.infolist()]
        member=next(n for n in z.namelist() if '_세종_' in n and n.endswith('.csv'))
        save(OUT/'raw/shops-sejong.csv',z.read(member))
    result={'version':'korean-public-acquisition-v1','recorded_at':now(),'sources':{},'failures':[
        {'source':'restaurants-national','url':'https://file.localdata.go.kr/file/general_restaurants/info',
         'result':'HTTP403 redirected /error.html in both requests and normal browser; nationwide file NOT acquired'},
        {'source':'seoul-original-files-tab','url':SEOU,'result':'No static attachments; used official sheet CSV download instead'}]}
    result['sources']['shops']={'source':URLS['shops'],'csv':'datasets/korea-v1/raw/shops-sejong.csv',
        'download_endpoint':url,'file_id':fid,'archive':str(zpath.relative_to(ROOT)),'zip_members':inventory,
        'scope':'One Sejong regional member; all regional members share one schema family, not independent',
        'reference_date':'2026-09-30 (edition name)','license':'이용허락범위 제한 없음 (official catalog)', 'encoding':'utf-8-sig'}
    for name,pk in [('markets','15012894'),('parking','15012896')]:
        result['sources'][name]=standard(name,pk)|{'source':URLS[name],'license':'Official JSON-LD links general portal terms without a named license; per-dataset scope unconfirmed. No raw redistribution.','reference_date':'per-row 데이터기준일자; see quality audit'}
    p=OUT/'raw/restaurants-seoul-permit2025.csv';sheet=OUT/'pages/seoul-sheet.html'
    get(SEOU,OUT/'pages/seoul-restaurants.html')
    get('https://data.seoul.go.kr/dataList/sheetView.do',sheet,params={'infId':'OA-23056','srvType':'S','serviceKind':'1'})
    data={'srvType':'S','infId':'OA-23056','serviceKind':'1','pageNo':'1','ssUserId':'SAMPLE_VIEW','strWhere':'','strOrderby':'','filterCol':'APVPERMYMD','txtFilter':'2025'}
    if not p.exists():
        # Endpoint is explicitly assembled by doAction('csv') in the official sheet HTML.
        if 'datafile.seoul.go.kr/bigfile/iot/sheet/' not in sheet.read_text('utf8'):raise RuntimeError('Official CSV route changed')
        r=requests.post('https://datafile.seoul.go.kr/bigfile/iot/sheet/csv/download.do',data=data,timeout=180);r.raise_for_status();save(p,r.content)
    result['sources']['restaurants']={'source':URLS['restaurants'],'actual_source':SEOU,'csv':str(p.relative_to(ROOT)),
        'download_endpoint':'https://datafile.seoul.go.kr/bigfile/iot/sheet/csv/download.do','POST_form':data,
        'scope':'Seoul only, APVPERMYMD contains2025; NOT nationwide standard dataset','encoding':'cp949',
        'reference_date':'page update2026-11-03, per-row update timestamps vary', 'license':'공공누리 제1유형: 출처표시, 상업적 이용/변경 가능 (Seoul official page)',
        'coordinate_warning':'Legacy 좌표정보(X/Y): national catalog EPSG:5174. Extra X좌표/Y좌표 CRS unverified; never treated as WGS84 degrees.'}
    for item in result['sources'].values():
        f=ROOT/item['csv'];heads,rows,enc=csv_load(f,item.get('encoding'))
        item.update(sha256=sha(f),bytes=f.stat().st_size,rows=len(rows),columns=len(heads),encoding=enc,
            raw_file_observed_mtime_utc=datetime.fromtimestamp(f.stat().st_mtime,timezone.utc).isoformat(),
            acquisition_time_basis='local original-file write mtime; manifest recorded separately')
    result['files']={str(p.relative_to(ROOT)): {'bytes':p.stat().st_size,'sha256':sha(p)} for p in [*(OUT/'raw').glob('*'),*(OUT/'derived').glob('*'),*(OUT/'pages').glob('*')] if p.is_file()}
    save(OUT/'acquisition.json',json.dumps(result,ensure_ascii=False,indent=2).encode('utf8'))
    print(json.dumps({k:{a:v[a] for a in ['rows','columns','encoding','sha256']} for k,v in result['sources'].items()},ensure_ascii=False,indent=2))
    return result
if __name__=='__main__':acquire()
