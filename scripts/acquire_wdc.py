"""Download archive URLs discovered in the official page; retain originals."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path,PurePosixPath
import sys
from urllib.parse import urljoin
import zipfile
import requests

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.records import json_bytes,now_iso

PAGE='https://webdatacommons.org/structureddata/smb/'

class Links(HTMLParser):
    def __init__(self):super().__init__();self.urls=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            href=dict(attrs).get('href')
            if href:self.urls.append(urljoin(PAGE,href))

def main():
    base=ROOT/'datasets/wdc_smb';raw=base/'raw';raw.mkdir(parents=True,exist_ok=True)
    report=base/'acquisition.json'
    if report.exists():print('Existing acquisition retained.');return
    session=requests.Session();session.headers['User-Agent']='SchemaMatchingResearchPrototype/1.0'
    page=session.get(PAGE,timeout=60);page.raise_for_status()
    (raw/'official-page.html').write_bytes(page.content)
    parser=Links();parser.feed(page.text)
    evidence={'source_url':PAGE,'downloaded_at':now_iso(),'page_sha256':hashlib.sha256(page.content).hexdigest(),'attempts':[],'files':[]}
    for filename in ('t2d_sm_wh.zip','t2d_sm_supplement_metadata.zip'):
        matches=[url for url in parser.urls if url.lower().endswith('/'+filename)]
        if len(set(matches))!=1:raise ValueError(f'Official link not uniquely discovered: {filename}')
        link=matches[0];response=session.get(link,timeout=90)
        evidence['attempts'].append({'url':link,'status':response.status_code,'final_url':response.url})
        if response.status_code!=200:
            # Ask the same official GitHub repository for THIS observed path's download URL.
            parts=link.split('github.com/',1)[1].split('/')
            owner,repo=parts[:2];file_path='/'.join(parts[4:])
            api=f'https://api.github.com/repos/{owner}/{repo}/contents/{file_path}?ref={parts[3]}'
            meta=session.get(api,timeout=60);meta.raise_for_status()
            response=session.get(meta.json()['download_url'],timeout=90)
            evidence['attempts'].append({'url':api,'status':meta.status_code,'alternative_url':meta.json()['download_url'],'status_download':response.status_code})
        response.raise_for_status()
        target=raw/filename
        with target.open('xb') as handle:handle.write(response.content)
        destination=raw/filename.removesuffix('.zip')
        destination.mkdir(exist_ok=False)
        with zipfile.ZipFile(target) as archive:
            for info in archive.infolist():
                rel=PurePosixPath(info.filename)
                final=(destination/Path(*rel.parts)).resolve()
                if rel.is_absolute() or not final.is_relative_to(destination.resolve()):raise ValueError('Unsafe archive path')
                if (info.external_attr>>16)&0o170000==0o120000:raise ValueError('Archive symlink rejected')
            archive.extractall(destination)
        evidence['files'].append({'official_link':link,'final_download_url':response.url,'archive':str(target.relative_to(ROOT)),
            'bytes':len(response.content),'sha256':hashlib.sha256(response.content).hexdigest(),'extracted_to':str(destination.relative_to(ROOT))})
    api='https://api.github.com/repos/wbsg-uni-mannheim/wdc-smb/license'
    license_meta=session.get(api,timeout=60)
    evidence['license_api_status']=license_meta.status_code
    if license_meta.ok:
        meta=license_meta.json();license_response=session.get(meta['download_url'],timeout=60);license_response.raise_for_status()
        (raw/'repository-LICENSE.txt').write_bytes(license_response.content)
        evidence['repository_license']={'source':meta['html_url'],'download_url':meta['download_url'],
            'spdx_id':meta.get('license',{}).get('spdx_id'),'sha256':hashlib.sha256(license_response.content).hexdigest()}
    evidence['inventory']=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'bytes':p.stat().st_size,
        'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(raw.rglob('*')) if p.is_file()]
    report.write_bytes(json_bytes(evidence))
    print(json.dumps({k:v for k,v in evidence.items() if k!='inventory'},ensure_ascii=True,indent=2))

if __name__=='__main__':main()
