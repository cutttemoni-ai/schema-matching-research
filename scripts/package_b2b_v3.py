"""Package existing synthetic artifacts, separating model inputs and author truth.
No inference, regeneration, scoring or modification of frozen inputs.
"""
import hashlib,json,sys,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from b2b_v3_campaign import ROOT,NEW_DATA,ART,RUN,read


def archive(path,items):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(items.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,11,4,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,data)
    with zipfile.ZipFile(path) as z:assert z.testzip() is None


def main():
    out=ROOT/'outputs/b2b-v3';out.mkdir(parents=True,exist_ok=True)
    note='합성 자료입니다. 원본 업무 명세 제공 조건. 실제 거래처 독립 평가가 아닙니다.\n'
    for folder,name,extra in [(NEW_DATA,'observed_model_inputs.zip','실제 동결 평가 입력. 정밀도 정오표가 별도로 있습니다.'),
            (ROOT/'datasets/b2b-v3-repaired-regression','repaired_regression_inputs.zip','동일 N01-N04의 정밀도 복구본. 새로운 구조의 독립 평가가 아닙니다.')]:
        inputs={p.relative_to(folder).as_posix():p.read_bytes() for p in (folder/'model_inputs').rglob('*') if p.is_file()}
        assert len(inputs)==32 and all(Path(n).name in ('source.csv','target_reference.csv','target_schema.json','source_context.json') for n in inputs)
        inputs['README.txt']=(note+extra+'\n정답/생성기는 포함하지 않습니다.\n').encode('utf-8')
        archive(out/name,inputs)
    files={}
    for folder in [NEW_DATA,ROOT/'datasets/b2b-v3-repaired-regression']:
        for p in folder.rglob('*'):
            if p.is_file():files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
    for p in ROOT.glob('B2B_V3_*'):
        if p.is_file() and p.name!='B2B_V3_ARTIFACT_MANIFEST.json':files[p.name]=p.read_bytes()
    for p in (ROOT/'authoring').glob('*.py'):files['authoring/'+p.name]=p.read_bytes()
    # Export only the active sealed evaluation and current regression derivative,
    # leaving pre-freeze development checkpoints in the local history.
    for j in read(ART/'evaluation-plan.json')['jobs']:
        for arm in (['C'] if j['arm']=='C' else ['v2','v3']):
            p=RUN/'predictions'/j['id']/(arm+'.json');files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
    for j in read(ART/'regression-plan.json')['jobs']:
        p=RUN/'predictions'/j['id']/'v3.json';files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
    for name in ('freeze.json','evaluation-plan.json','evaluation-plan-seal.json','predictions-seal.json','regression-plan.json'):
        p=ART/name;files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
    for name in ('b2b_v3_campaign.py','score_b2b_v3.py','report_b2b_v3.py','check_b2b_v3_precision_repair.py'):
        p=ROOT/'scripts'/name;files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
    for name in ('b2b_v3.py','b2b_v3_adapter.py'):
        p=ROOT/'schema_match'/name;files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
    p=ROOT/'docs/B2B_V3_SOURCE_CONTRACT.md';files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
    files['AUTHOR_ONLY_README.txt']=(note+'작성자/평가자 전용. 정답·생성 규칙 포함. 모델/추론 입력으로 제공하지 마세요.\n원본과 복구본 결과를 혼합하거나 독립 평가로 재명명하지 마세요.\n').encode('utf-8')
    archive(out/'author_evaluator_bundle.zip',files)
    sums={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob('*.zip'))}
    (out/'SHA256SUMS.txt').write_text(''.join(f'{h}  {n}\n' for n,h in sums.items()),encoding='utf-8')
    print(json.dumps({'model_input_files_each':32,'author_only_entries':len(files),'artifacts':sums},indent=2))


if __name__=='__main__':main()
