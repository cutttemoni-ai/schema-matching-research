"""App accounts, salted scrypt, server-side opaque sessions. No IAM header trust."""
import hashlib,hmac,os,re,secrets,time,uuid
from .storage import read_json,Conflict

COOKIE='schema_review_session'
SESSION_SECONDS=12*60*60
class AuthError(Exception):pass
class Throttled(Exception):pass

class Accounts:
    def __init__(self,objects,*,demo_only=None,demo_key=None,identity_objects=None):
        self.objects=objects
        self.identities=identity_objects or objects
        self.demo_only=os.getenv('DEMO_LOGIN_ONLY','').lower()=='true' if demo_only is None else demo_only
        self.demo_key=demo_key or os.getenv('DEMO_CREDENTIALS_OBJECT','review-v2/config/demo-login.json')
    def _demo_config(self):
        """Private server object, containing only a salted hash, never plaintext."""
        config,_=read_json(self.objects,self.demo_key)
        if (not isinstance(config,dict) or config.get('scheme')!='scrypt-n16384-r8-p1'
            or not re.fullmatch(r'[a-f0-9]{32}',str(config.get('salt','')))
            or not re.fullmatch(r'[a-f0-9]{128}',str(config.get('password_hash','')))):
            raise AuthError('데모 로그인 설정을 확인할 수 없습니다. 운영 담당자에게 문의하세요.')
        try:self._username(config.get('username'))
        except AuthError:raise AuthError('데모 로그인 설정을 확인할 수 없습니다. 운영 담당자에게 문의하세요.')
        return config
    def _demo_revision(self,config):
        return hashlib.sha256((config['username']+':'+config['salt']+':'+config['password_hash']).encode()).hexdigest()
    def rate(self,category,maximum,window):
        prefix=f'review-v2/rate/{category}/{int(time.time()//window)}/'
        for n in range(maximum):
            try:self.objects.write(prefix+f'{n:03}.json',{'at':time.time()},0);return
            except Conflict:continue
        raise Throttled('요청이 많습니다. 잠시 후 다시 시도해 주세요.')
    def _username(self,name):
        if not isinstance(name,str) or not re.fullmatch(r'[a-zA-Z0-9가-힣][a-zA-Z0-9가-힣_.-]{2,31}',name):raise AuthError('아이디는 한글·영문·숫자와 ._- 조합3~32자입니다.')
        return name.casefold()
    def _key(self,name):return 'review-v2/accounts/'+hashlib.sha256(name.encode()).hexdigest()+'.json'
    def _account(self,normal):
        key=self._key(normal);account,_=read_json(self.identities,key)
        if account is None and self.identities is not self.objects:
            # Retain an existing personal UID on first use of durable identities.
            # Do not migrate sessions/demo identities or create an alias UID.
            previous,_=read_json(self.objects,key)
            if previous:
                try:self.identities.write(key,previous,0)
                except Conflict:
                    account,_=read_json(self.identities,key)
                    if account!=previous:raise AuthError('계정 이전 충돌을 담당자에게 확인해 주세요.')
                account=previous
        return account
    def _hash(self,password,salt):return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1,maxmem=64*1024*1024).hex()
    def register(self,name,password):
        if self.demo_only:raise AuthError('데모에서는 새 계정을 만들 수 없습니다.')
        self.rate('registration',20,86400);normal=self._username(name)
        if not isinstance(password,str) or not 12<=len(password)<=128:raise AuthError('비밀번호는12~128자여야 합니다.')
        if self._account(normal):raise AuthError('이미 사용 중인 아이디입니다.')
        salt=secrets.token_hex(16);account={'uid':uuid.uuid4().hex,'username':name,'password_hash':self._hash(password,salt),'salt':salt,'created_at':time.time(),'scheme':'scrypt-n16384-r8-p1'}
        try:self.identities.write(self._key(normal),account,0)
        except Conflict:raise AuthError('이미 사용 중인 아이디입니다.')
        return self.session(account)
    def login(self,name,password):
        self.rate('login',50,300)
        try:normal=self._username(name)
        except AuthError:raise AuthError('아이디 또는 비밀번호를 확인해 주세요.')
        if not isinstance(password,str) or len(password)>128:raise AuthError('아이디 또는 비밀번호를 확인해 주세요.')
        if self.demo_only:
            config=self._demo_config()
            password_ok=hmac.compare_digest(self._hash(password,config['salt']),config['password_hash'])
            name_ok=hmac.compare_digest(normal.encode(),self._username(config['username']).encode())
            if not password_ok or not name_ok:raise AuthError('아이디 또는 비밀번호를 확인해 주세요.')
            # Shared credentials authenticate access, not ownership. A fresh
            # random owner on each login prevents cross-browser account sharing.
            return self.session({'uid':uuid.uuid4().hex,'username':config['username']},
                authentication='demo-password-session',credential_revision=self._demo_revision(config))
        account=self._account(normal)
        salt=account['salt'] if account else '00'*16;expected=account['password_hash'] if account else '00'*64
        if not hmac.compare_digest(self._hash(password,salt),expected) or not account:raise AuthError('아이디 또는 비밀번호를 확인해 주세요.')
        return self.session(account)
    def session(self,account,*,authentication='app-password-session',credential_revision=None):
        token=secrets.token_hex(32);csrf=secrets.token_hex(24)
        record={'uid':account['uid'],'username':account['username'],'csrf':csrf,'expires_at':time.time()+SESSION_SECONDS,'authentication':authentication}
        if credential_revision:record['credential_revision']=credential_revision
        self.objects.write('review-v2/auth-sessions/'+hashlib.sha256(token.encode()).hexdigest()+'.json',record,0)
        return token,record
    def authenticate(self,token):
        if not isinstance(token,str) or not re.fullmatch(r'[a-f0-9]{64}',token):raise AuthError('로그인이 필요합니다.')
        v,_=read_json(self.objects,'review-v2/auth-sessions/'+hashlib.sha256(token.encode()).hexdigest()+'.json')
        if not v or v['expires_at']<=time.time():raise AuthError('로그인 세션이 만료됐습니다. 다시 로그인해 주세요.')
        if self.demo_only:
            if v.get('authentication')!='demo-password-session':raise AuthError('데모 계정으로 다시 로그인해 주세요.')
            if not hmac.compare_digest(v.get('credential_revision',''),self._demo_revision(self._demo_config())):
                raise AuthError('로그인 설정이 변경됐습니다. 다시 로그인해 주세요.')
        elif v.get('authentication')=='demo-password-session':raise AuthError('다시 로그인해 주세요.')
        return v
    def logout(self,token):
        key='review-v2/auth-sessions/'+hashlib.sha256(token.encode()).hexdigest()+'.json';_,gen=self.objects.read(key)
        if gen:self.objects.delete(key,gen)
