"""Local candidate only. Does not deploy, seed business facts or call a model.

Optional --seed-reviewer creates a disposable local review account with the
documented synthetic password. Never used with SERVICE_BUCKET or K_SERVICE.
"""
import argparse
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8510)
    parser.add_argument('--seed-reviewer',action='store_true');args=parser.parse_args()
    if os.getenv('K_SERVICE') or os.getenv('SERVICE_BUCKET') or os.getenv('B2B_RULES_BUCKET'):
        raise SystemExit('Local preview must not use Cloud Run or a cloud bucket')
    os.environ['DEMO_LOGIN_ONLY']='false';os.environ['B2B_WEB_ENABLED']='true'
    from schema_match.config import ROOT
    os.environ.setdefault('REVIEW_LOCAL_ROOT',str(ROOT/'runs/b2b-web-preview'))
    if args.seed_reviewer:
        from web_review.auth import Accounts,AuthError
        from web_review.storage import LocalObjects
        accounts=Accounts(LocalObjects(os.environ['REVIEW_LOCAL_ROOT']),demo_only=False)
        try:accounts.register('preview-reviewer','synthetic-preview-only-2026')
        except AuthError as e:
            if str(e)!='이미 사용 중인 아이디입니다.':raise
    import uvicorn
    uvicorn.run('web_review.app:app',host='127.0.0.1',port=args.port,access_log=False)


if __name__=='__main__':main()
