"""Build allowlist/import smoke without a cloud build or deployment."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT


def main():
    out=ROOT/'outputs/b2b-web/build-context';out.mkdir(parents=True,exist_ok=True)
    names=[line[1:] for line in (ROOT/'.dockerignore').read_text().splitlines() if line.startswith('!') and not line.endswith('/')]
    names=sorted(set(n for n in names if (ROOT/n).is_file()))
    assert not any(n.startswith(('runs/','datasets/','research-artifacts/','authoring/')) or '.env' in n for n in names)
    for n in names:
        dest=out/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,dest)
    code='import sys;sys.path.insert(0,sys.argv[1]);from web_review.app import app;assert app.state.b2b;print("candidate image imports passed")'
    result=subprocess.run([sys.executable,'-I','-c',code,str(out)],cwd=out,text=True,capture_output=True)
    if result.returncode:raise RuntimeError(result.stderr)
    manifest=dict(type='allowlist and isolated Python import smoke; Docker daemon unavailable, not image build',passed=True,
                  files={n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in names},private_data_included=False)
    (ROOT/'B2B_WEB_BUILD_CHECK.json').write_bytes((json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    print(result.stdout.strip(),len(names),'allowlisted files')


if __name__=='__main__':main()
