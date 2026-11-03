"""Read official remote ZIP directory before selecting bounded members; never fetch entire archive."""
import sys,io,json,time,zipfile,hashlib
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'datasets/product-quality-v1';OUT.mkdir(parents=True,exist_ok=True)
URL='https://zenodo.org/records/5084605/files/Valentine-datasets.zip?download=1'

class RemoteZip(io.RawIOBase):
    def __init__(self,url,size):self.url=url;self.size=size;self.pos=0;self.events=[]
    def seekable(self):return True
    def readable(self):return True
    def tell(self):return self.pos
    def seek(self,offset,whence=0):
        self.pos=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        return self.pos
    def read(self,n=-1):
        if n<0:n=self.size-self.pos
        n=min(n,self.size-self.pos)
        if n<=0:return b''
        if n>32*1024*1024:raise ValueError('Large read refused; metadata/member bound32MB')
        first=self.pos;last=first+n-1
        response=requests.get(self.url,headers={'Range':f'bytes={first}-{last}'},stream=True,timeout=90)
        try:
            if response.status_code!=206:raise ValueError('Range not supported; full archive download refused: '+str(response.status_code))
            if response.headers.get('Content-Range')!=f'bytes {first}-{last}/{self.size}':raise ValueError('Unexpected range')
            raw=response.content
            if len(raw)!=n:raise ValueError('Incomplete range')
        finally:response.close()
        self.events.append({'start':first,'end':last,'bytes':n,'sha256':hashlib.sha256(raw).hexdigest()});self.pos+=n
        return raw

def main():
    if sys.argv[1]=='list':
        remote=RemoteZip(URL,602150347)
        with zipfile.ZipFile(remote) as archive:
            entries=[{'name':v.filename,'uncompressed':v.file_size,'compressed':v.compress_size,'offset':v.header_offset,'CRC':v.CRC} for v in archive.infolist()]
        result={'url':URL,'official_page':'https://zenodo.org/records/5084605','version':'v1 / 2021-07-09','published_archive_bytes':602150347,
            'published_archive_MD5':'98da6d6701806538e5c685f4426b95f6','full_archive_MD5_verified':False,'entries':entries,'range_requests':remote.events,'at_unix':time.time()}
        (OUT/'valentine-remote-directory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'entries':len(entries),'directory_bytes_fetched':sum(v['bytes'] for v in remote.events),'top_folders':sorted({v['name'].split('/')[1] if '/' in v['name'] else v['name'] for v in entries}),'first_entries':entries[:12]}))
    elif sys.argv[1]=='extract':
        manifest=json.loads((OUT/'selection.json').read_bytes());remote=RemoteZip(URL,602150347)
        with zipfile.ZipFile(remote) as archive:
            records=[]
            for name in manifest['members']:
                target=(OUT/'valentine'/name).resolve();target.relative_to((OUT/'valentine').resolve())
                if target.exists():raise FileExistsError(target)
                raw=archive.read(name);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
                records.append({'member':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'ZIP_CRC_verified':True})
        (OUT/'acquisition.json').write_text(json.dumps({'url':URL,'at_unix':time.time(),'files':records,'range_requests':remote.events,'full_archive_downloaded':False},indent=2),encoding='utf-8')
        print(json.dumps({'selected_files':len(records),'uncompressed_bytes':sum(v['bytes'] for v in records),'network_bytes':sum(v['bytes'] for v in remote.events)}))

if __name__=='__main__':main()
