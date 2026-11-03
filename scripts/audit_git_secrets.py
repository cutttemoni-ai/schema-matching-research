"""Scan prospective Git files/history; output only path/rule, never secret values."""
import argparse, json, re, subprocess, sys
from pathlib import Path

RULES = {
    'google_api_key': rb'AIza[0-9A-Za-z_-]{35}',
    'github_token': rb'gh[opusr]_[A-Za-z0-9_]{25,}',
    'google_access_token': rb'ya29\.[A-Za-z0-9_.-]{35,}',
    'aws_access_key': rb'(?:AKIA|ASIA)[A-Z0-9]{16}',
    'private_key': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'secret_assignment': rb'''(?i)(?:refresh_token|client_secret|access_token|api_key|password)["']?\s*[:=]\s*["'][A-Za-z0-9_/+.=-]{28,}["']''',
    'oauth_authorization_url': rb'https://accounts\.google\.com/(?:o/oauth2|o/oauth)/[^\s"<>]*\?[^\s"<>]*(?:client_id|code_challenge|redirect_uri)=',
}


def scan():
    p = argparse.ArgumentParser(); p.add_argument('--history', action='store_true'); a=p.parse_args()
    findings=[]; checked=0
    if a.history:
        refs=subprocess.run(['git','rev-list','--objects','--all'],capture_output=True,check=True).stdout.splitlines()
        objects=[]
        for line in refs:
            fields=line.decode().split(' ',1)
            if len(fields)==2 and subprocess.run(['git','cat-file','-t',fields[0]],capture_output=True,check=True).stdout.strip()==b'blob':
                objects.append((fields[1], subprocess.run(['git','cat-file','blob',fields[0]],capture_output=True,check=True).stdout))
    else:
        paths=subprocess.run(['git','ls-files','--cached','-z'],capture_output=True,check=True).stdout.split(b'\0')
        objects=[(x.decode(),Path(x.decode()).read_bytes()) for x in paths if x]
    for name,raw in objects:
        checked+=1
        for rule,pattern in RULES.items():
            if re.search(pattern,raw): findings.append({'path':name,'rule':rule})
    print(json.dumps({'history':a.history,'checked_blobs':checked,'findings':findings,'secret_values_printed':False}))
    return int(bool(findings))


if __name__=='__main__': sys.exit(scan())
