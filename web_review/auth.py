"""App accounts, salted scrypt, server-side opaque sessions. No IAM header trust."""
import hashlib,hmac,re,secrets,time,uuid
from .storage import read_json,Conflict

COOKIE='schema_review_session'
SESSION_SECONDS=12*60*60
class AuthError(Exception):pass
class Throttled(Exception):pass

class Accounts:
    def __init__(self,objects):self.objects=objects
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
    def _hash(self,password,salt):return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1,maxmem=64*1024*1024).hex()
    def register(self,name,password):
        self.rate('registration',20,86400);normal=self._username(name)
        if not isinstance(password,str) or not 12<=len(password)<=128:raise AuthError('비밀번호는12~128자여야 합니다.')
        salt=secrets.token_hex(16);account={'uid':uuid.uuid4().hex,'username':name,'password_hash':self._hash(password,salt),'salt':salt,'created_at':time.time(),'scheme':'scrypt-n16384-r8-p1'}
        try:self.objects.write(self._key(normal),account,0)
        except Conflict:raise AuthError('이미 사용 중인 아이디입니다.')
        return self.session(account)
    def login(self,name,password):
        self.rate('login',50,300)
        try:normal=self._username(name)
        except AuthError:raise AuthError('아이디 또는 비밀번호를 확인해 주세요.')
        if not isinstance(password,str) or len(password)>128:raise AuthError('아이디 또는 비밀번호를 확인해 주세요.')
        account,_=read_json(self.objects,self._key(normal))
        salt=account['salt'] if account else '00'*16;expected=account['password_hash'] if account else '00'*64
        if not hmac.compare_digest(self._hash(password,salt),expected) or not account:raise AuthError('아이디 또는 비밀번호를 확인해 주세요.')
        return self.session(account)
    def session(self,account):
        token=secrets.token_hex(32);csrf=secrets.token_hex(24)
        record={'uid':account['uid'],'username':account['username'],'csrf':csrf,'expires_at':time.time()+SESSION_SECONDS,'authentication':'app-password-session'}
        self.objects.write('review-v2/auth-sessions/'+hashlib.sha256(token.encode()).hexdigest()+'.json',record,0)
        return token,record
    def authenticate(self,token):
        if not isinstance(token,str) or not re.fullmatch(r'[a-f0-9]{64}',token):raise AuthError('로그인이 필요합니다.')
        v,_=read_json(self.objects,'review-v2/auth-sessions/'+hashlib.sha256(token.encode()).hexdigest()+'.json')
        if not v or v['expires_at']<=time.time():raise AuthError('로그인 세션이 만료됐습니다. 다시 로그인해 주세요.')
        return v
    def logout(self,token):
        key='review-v2/auth-sessions/'+hashlib.sha256(token.encode()).hexdigest()+'.json';_,gen=self.objects.read(key)
        if gen:self.objects.delete(key,gen)
