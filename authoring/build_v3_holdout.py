"""AUTHOR/EVALUATOR ONLY. Precision-repaired REGRESSION data, not a new holdout.

The original observed generator is build_v3_holdout_observed_v1.py. This repair
retains the SAME families/seed/canonical samples; do not call it independent new
structure validation. No original evaluation input, truth or score is overwritten.
"""
import csv,hashlib,json,random,sys
from collections import defaultdict
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from b2b_v3_campaign import ROOT,ART,NEW_DATA as OBSERVED_DATA,OLD_DATA,read,write,verify_freeze,journal

NEW_DATA=ROOT/'datasets/b2b-v3-repaired-regression'

NOTICE='합성 자료: 모든 거래처·상품·주문은 가상이며 실제 기업·거래 자료가 아닙니다.'
BASE_SEED=2026110403
PROFILES={
    1:dict(decimal=',',group='.',scale='1000',gross=True,calendar='gregorian_json',code='nested_json',quantity='nested_counts',basis='row_varying'),
    2:dict(decimal=',',group=' ',scale='0.01',gross=False,calendar='iso_week',code='three_parts',quantity='two_counts',basis='row_varying'),
    3:dict(decimal='.',group=',',scale='1',gross=True,calendar='epoch_ms',code='array_parts',quantity='json_dynamic_unit',basis='row_varying'),
    4:dict(decimal='.',group='',scale='100',gross=False,calendar='ordinal',code='two_padded_parts',quantity='three_tier_counts',basis='row_varying'),
}


def seed(*parts):return int.from_bytes(hashlib.sha256(':'.join(map(str,(BASE_SEED,*parts))).encode()).digest()[:8],'big')
def round_won(x):return int(Decimal(str(x)).quantize(Decimal(1),rounding=ROUND_HALF_UP))
def dump(p,obj):write(p,obj)
def fmt(n,p):
    text=format(Decimal(str(n)),'f');whole,_,frac=text.partition('.')
    if p['group']:
        chunks=[]
        while whole:chunks.insert(0,whole[-3:]);whole=whole[:-3]
        whole=p['group'].join(chunks)
    return whole+(p['decimal']+frac.rstrip('0') if frac.rstrip('0') else '')
def nf(p):return {'decimal':p['decimal'],'group':p['group'],'remove':['₩']}
def ref(column,path=''):return {'column':column,**({'path':path} if path else {})}
def factor(column,unit='BOX'):return {'ref':ref(column),'dimension':'EA/'+unit}


def schema(kind):
    spec=read(OLD_DATA/'schemas'/f'{kind}.json')
    spec['schema_id']='b2b-v3-source-contract-'+kind
    spec['notice']=NOTICE
    for f in spec['fields']:
        k=f['id'];unit=f.get('unit') or ''
        if unit.startswith('KRW'):
            basis='EA' if unit.endswith('/EA') else 'none'
            tax='exclusive' if k in ('sale_price','purchase_price','unit_price','line_amount') else 'value'
            c={'kind':'money','currency':'KRW','scale':'1','basis':basis,'tax_basis':tax}
        elif k=='quantity':c={'kind':'quantity','basis':'EA','integral':True,'positive':True}
        elif k=='pack_size':c={'kind':'count','dimension':'EA/BOX','integral':True,'positive':True}
        elif k=='tax_rate':c={'kind':'ratio','scale':'1'}
        elif k in ('sales_unit','quantity_unit'):c={'kind':'unit_label','basis':'EA'}
        elif k in ('product_code','barcode','order_id','line_id'):c={'kind':'identifier'}
        elif k=='order_date':c={'kind':'calendar'}
        else:c={'kind':'text'}
        f['unit_contract']=c
    return spec


def code(n,sample,i):
    head=f'00{"S" if sample=="source" else "R"}{n}'
    if n==1:return head+'-'+f'{i+1:05d}'
    if n==2:return head+':B:'+f'{i+1:05d}'
    if n==3:return head+'.'+f'{i+1:05d}'
    return head+'/'+f'{i+1:05d}'


def products(n,count,sample):
    rng=random.Random(seed(n,sample,'products'));out=[]
    for i in range(count):
        sale=rng.randrange(80,9000)*10;purchase=round_won(sale*Decimal(str(rng.choice([.55,.65,.8]))))
        out.append(dict(product_code=code(n,sample,i),barcode=f'28{n:02d}{1 if sample=="source" else 7}{i:08d}',
            product_name=f'합성-새구조-N{n:02d}-{sample}-{i:04d}',option=rng.choice(['푸른색/기본','흰색/넓음','검은색/소형']),
            specification=f'{rng.choice([50,100,200,300,500])} mm',sales_unit='EA',pack_size=rng.choice([8,12,20]),
            sale_price=sale,purchase_price=purchase,category=f'합성분류-N{n:02d}'))
    return out


def orders(n,catalog,count,sample):
    rng=random.Random(seed(n,sample,'orders'));out=[];g=0
    while len(out)<count:
        lines=[];d=date(2027 if sample=='source' else 2028,1,1)+timedelta(days=rng.randrange(290))
        for li in range(min(rng.randint(2,4),count-len(out))):
            prod=rng.choice(catalog);qty=rng.randint(1,9)*6 if n==3 else rng.randint(1,80)
            if n==4:
                extra=rng.choice([120,240,480]);pallet=rng.randint(0,2);boxes=rng.randint(0,3);loose=rng.randint(1,prod['pack_size']-1)
                qty=pallet*extra+boxes*prod['pack_size']+loose
            else:extra=pallet=boxes=loose=None
            unit=round_won(prod['sale_price']*Decimal(str(rng.choice([.9,1,1.1]))));amount=qty*unit
            discount=round_won(Decimal(amount)*Decimal(str(rng.choice([0,.03,.07]))));rate=rng.choice([0,.05,.1,.2])
            tax=round_won(Decimal(amount-discount)*Decimal(str(rate)))
            row=dict(order_id=f'SYN-NEW-N{n:02d}-{sample}-{g:04d}',line_id=f'{li+1:03d}',order_date=d.isoformat(),
                product_code=prod['product_code'],quantity=qty,quantity_unit='EA',pack_size=prod['pack_size'],
                unit_price=unit,line_amount=amount,discount_amount=discount,tax_amount=tax,line_total=amount-discount+tax,tax_rate=rate)
            if n==4:row['_source_counts']={'pallet':pallet,'boxes':boxes,'loose':loose,'pallet_size':extra}
            lines.append(row)
        total=sum(r['line_total'] for r in lines)
        for row in lines:row['order_total']=total
        out.extend(lines);g+=1
    return out


def source_layout(n,kind,canonical):
    p=PROFILES[n];spec=schema(kind);keys=[f['id'] for f in spec['fields']]
    # New opaque dictionaries, declared independently from old D/E headers.
    names={k:f'{["新帳","ledger","항목","cell"][n-1]}_{i+1:02d}' for i,k in enumerate(keys)}
    meta={};groups=[];bindings=[];excluded=set();extra={};encoders={}
    def field(name,description,**kw):meta[name]={'description':description,**kw}
    def binding(src,targets,status='mapped',composition=False):
        bindings.append(dict(binding_id=f'b{len(bindings):02d}',source_columns=list(src),semantic_targets=list(targets),status=status,
            cardinality='none' if not targets else 'one_to_one' if len(src)==len(targets)==1 else 'many_to_one' if len(targets)==1 else 'one_to_many' if len(src)==1 else 'many_to_many',
            requires_composition=composition,candidate_targets=[]))
    def text(name,key,description=None,path=''):
        field(name,description or next(f['label'] for f in spec['fields'] if f['id']==key),value_path=path)
        encoders[name]=lambda row,i,key=key: str(row[key])
    unit_col=names['sales_unit' if kind=='products' else 'quantity_unit'];pack_col=names['pack_size']
    price_basis_col=unit_col if kind=='products' else 'basis_note'
    rate_col='quote_tax_note' if kind=='products' else names['tax_rate']
    unit_codes={'CT':'BOX','PI':'EA'} if n!=3 or kind=='products' else {'DZ':'DOZEN','PI':'EA'}
    factors={'BOX':factor(pack_col)}
    if 'DOZEN' in unit_codes.values():factors['DOZEN']='12'
    def source_code(i):return list(unit_codes)[i%2]
    def source_basis(i):return unit_codes[source_code(i)]
    def source_factor(row,i):return Decimal(1) if source_basis(i)=='EA' else Decimal(12) if source_basis(i)=='DOZEN' else Decimal(row['pack_size'])
    def input_rate(row,i):return Decimal(str(row['tax_rate'])) if kind=='orders' else Decimal(str([0,.05,.1,.2][i%4]))
    for f in spec['fields']:
        key=f['id'];name=names[key];label=f['label'];target=f['unit_contract']
        if key in ('product_code','order_date','quantity') and (key!='product_code' or kind=='products'):
            continue
        if key in ('sales_unit','quantity_unit'):
            codes=unit_codes if kind=='products' else {'SUM':'EA'}
            field(name,label+'；원본 계량 코드의 의미는 unit_codes에 명시',unit_codes=codes,factors=factors)
            encoders[name]=(lambda row,i:source_code(i)) if kind=='products' else (lambda row,i:'SUM')
        elif target['kind']=='money':
            price=key in ('sale_price','purchase_price','unit_price')
            u={'kind':'money','currency':'KRW','scale':p['scale'],'tax_basis':'inclusive' if price and p['gross'] else 'exclusive' if price or key=='line_amount' else 'value'}
            if price:
                u.update(basis_ref=ref(price_basis_col),unit_codes=unit_codes,factors=factors)
                if p['gross']:u.update(rate_ref=ref(rate_col),rate_unit='percent',rate_number_format=nf(p))
            # Deliberately keep one clear semantic field per partner without the
            # necessary tax-basis evidence. It MUST remain in the denominator.
            if kind=='products' and key=='purchase_price':u.pop('tax_basis')
            path='/payload/value' if n in (1,3) else ''
            if price and path:u['basis_ref']=ref(name,'/payload/basis')
            description=label+'；통화/배율/가격기준은 원본 unit 정의 참조'
            if key=='purchase_price':description+='；과세 포함 여부 미제공'
            field(name,description,value_path=path,number_format=nf(p),unit=u)
            def encode_money(row,i,key=key,price=price,path=path):
                v=Decimal(str(row[key]))
                if price:
                    v*=source_factor(row,i)
                    if p['gross']:v*=1+input_rate(row,i)
                result='₩'+fmt(v/Decimal(p['scale']),p)
                # Independent rendering inverse check; do not use the engine.
                serialized=result.replace('₩','')
                if p['group']:serialized=serialized.replace(p['group'],'')
                rendered=Decimal(serialized.replace(p['decimal'],'.'))*Decimal(p['scale'])
                if price:
                    rendered/=source_factor(row,i)
                    if p['gross']:rendered/=1+input_rate(row,i)
                assert rendered==Decimal(str(row[key])), 'Serialized source price/rate loses exact business value'
                return json.dumps({'payload':{'value':result,'basis':source_code(i)}},ensure_ascii=False,separators=(',',':')) if path else result
            encoders[name]=encode_money
        elif key=='pack_size':
            field(name,label+' (EA/BOX)',number_format=nf(p),unit={'kind':'count','dimension':'EA/BOX'})
            encoders[name]=lambda row,i:str(row['pack_size'])
        elif key=='tax_rate':
            field(name,label+'；百分率 표기',number_format=nf(p),unit={'kind':'ratio','scale':'0.01'})
            encoders[name]=lambda row,i:fmt(Decimal(str(row['tax_rate']))*100,p)
        elif key=='product_code' and kind=='orders' and n==3:
            text(name,key,path='/key');encoders[name]=lambda row,i:json.dumps({'key':row['product_code']},separators=(',',':'))
        elif key=='barcode' and n==3:
            text(name,key,path='/scan/0');encoders[name]=lambda row,i:json.dumps({'scan':[row['barcode']]},separators=(',',':'))
        else:text(name,key)
        binding([name],[key])
    if kind=='products':
        name=names['product_code'];desc='상품코드；회사 내부 식별 문자열은 다음 구성요소를 순서대로 결합'
        def head(row):return row['product_code'].split(['- ',':','.','/'][n-1].strip())[0]
        if n==1:
            field(name,desc+'；중첩 객체의 두 성분')
            encoders[name]=lambda row,i:json.dumps({'v':{'head':head(row),'index':str(i+1)}},separators=(',',':'))
            parts=[{'ref':ref(name,'/v/head')},{'ref':ref(name,'/v/index'),'width':5,'pad':'0'}];members=[name];sep='-'
        elif n==2:
            members=[name,'key_segment','key_sequence'];parts=[{'ref':ref(members[0])},{'ref':ref(members[1])},{'ref':ref(members[2]),'width':5,'pad':'0'}];sep=':'
            for col,d in zip(members,['접두','중간','순번']):field(col,desc+'；'+d+' 성분')
            encoders[members[0]]=lambda row,i:head(row);encoders[members[1]]=lambda row,i:'B';encoders[members[2]]=lambda row,i:str(i+1)
        elif n==3:
            field(name,desc+'；배열의 두 성분')
            encoders[name]=lambda row,i:json.dumps({'segments':[head(row),str(i+1)]},separators=(',',':'))
            members=[name];parts=[{'ref':ref(name,'/segments/0')},{'ref':ref(name,'/segments/1'),'width':5,'pad':'0'}];sep='.'
        else:
            members=[name,'key_sequence'];sep='/'
            parts=[{'ref':ref(name)},{'ref':ref('key_sequence'),'width':5,'pad':'0'}]
            for col,d in zip(members,['접두','순번']):field(col,desc+'；'+d+' 성분')
            encoders[name]=lambda row,i:head(row);encoders['key_sequence']=lambda row,i:str(i+1)
        groups.append(dict(group_id='identifier-format',kind='identifier',members=members,description=desc,parts=parts,separator=sep))
        binding(members,['product_code'],composition=True)
        field(rate_col,'견적 표기용 세율 (상품 표준에 대응 항목 없음)',semantic_status='operational_only',number_format=nf(p),unit={'kind':'ratio','scale':'0.01'})
        encoders[rate_col]=lambda row,i:fmt(input_rate(row,i)*100,p)
        binding([rate_col],[],status='unmapped')
        field('undefined_measure','의미 정의가 제공되지 않은 숫자 지표',semantic_status='undefined')
        encoders['undefined_measure']=lambda row,i:'777';binding(['undefined_measure'],[],status='ambiguous')
    else:
        # Calendar shapes absent from old D/E flat formats.
        date_col=names['order_date'];desc='주문일；고객 주문 접수일을 지정된 달력 구성으로 기록'
        if n==1:
            field(date_col,desc+'；중첩 Gregorian 객체')
            encoders[date_col]=lambda row,i:json.dumps({'calendar':{'Y':date.fromisoformat(row['order_date']).year,'M':date.fromisoformat(row['order_date']).month,'D':date.fromisoformat(row['order_date']).day}},separators=(',',':'))
            members=[date_col];cg=dict(calendar='gregorian',parts={k:ref(date_col,'/calendar/'+v) for k,v in [('year','Y'),('month','M'),('day','D')]})
        elif n==2:
            members=[date_col,'week_component','weekday_component']
            for col,part in zip(members,['ISO week-year','ISO week','ISO weekday']):field(col,desc+'；'+part)
            for index,col in enumerate(members):encoders[col]=lambda row,i,index=index:str(date.fromisoformat(row['order_date']).isocalendar()[index])
            cg=dict(calendar='iso_week',parts=dict(zip(('year','week','weekday'),map(ref,members))))
        elif n==3:
            field(date_col,desc+'；1970 UTC 기준 Unix 밀리초, 영업일 시간대 Asia/Seoul')
            encoders[date_col]=lambda row,i:str(int((datetime.fromisoformat(row['order_date']+'T03:00:00+00:00')-datetime(1970,1,1,tzinfo=timezone.utc)).total_seconds()*1000))
            members=[date_col];cg=dict(calendar='epoch',value_ref=ref(date_col),origin='1970-01-01T00:00:00+00:00',epoch_unit='milliseconds',timezone='Asia/Seoul')
        else:
            members=[date_col,'ordinal_component'];field(date_col,desc+'；연도');field(members[1],desc+'；연중 일차')
            encoders[date_col]=lambda row,i:str(date.fromisoformat(row['order_date']).year)
            encoders[members[1]]=lambda row,i:str(date.fromisoformat(row['order_date']).timetuple().tm_yday)
            cg=dict(calendar='ordinal',parts={'year':ref(date_col),'ordinal':ref(members[1])})
        groups.append(dict(group_id='order-calendar',kind='calendar',members=members,description=desc,**cg));binding(members,['order_date'],composition=True)
        qcol=names['quantity'];qdesc='수량；이 주문 행의 총 낱개 수량(EA)을 구성하는 출고 단위 성분'
        if n==1:
            field(qcol,qdesc+'；JSON 객체에 BOX 수와 잔여 EA를 각각 보관')
            encoders[qcol]=lambda row,i:json.dumps({'dispatch':{'boxes':str(row['quantity']//row['pack_size']),'loose':str(row['quantity']%row['pack_size'])}},separators=(',',':'))
            members=[qcol];terms=[{'count':ref(qcol,'/dispatch/boxes'),'unit':'BOX'},{'count':ref(qcol,'/dispatch/loose'),'unit':'EA'}]
        elif n==2:
            members=[qcol,'remaining_each'];field(qcol,qdesc+'；BOX 수');field(members[1],qdesc+'；잔여 낱개')
            encoders[qcol]=lambda row,i:str(row['quantity']//row['pack_size']);encoders[members[1]]=lambda row,i:str(row['quantity']%row['pack_size'])
            terms=[{'count':ref(qcol),'unit':'BOX'},{'count':ref(members[1]),'unit':'EA'}]
        elif n==3:
            field(qcol,qdesc+'；JSON 수량과 행별 단위 코드',value_path='/amount',number_format=nf(p),
                unit={'kind':'quantity','basis_ref':ref(qcol,'/unit'),'unit_codes':unit_codes,'factors':factors})
            encoders[qcol]=lambda row,i:json.dumps({'amount':fmt(Decimal(row['quantity'])/source_factor(row,i),p),'unit':source_code(i)},separators=(',',':'))
            binding([qcol],['quantity']);members=[];terms=[]
        else:
            members=[qcol,'pallet_count','remaining_each']
            for col,label in zip(members,['BOX 수','PALLET 수','잔여 EA']):field(col,qdesc+'；'+label)
            encoders[qcol]=lambda row,i:str(row['_source_counts']['boxes']);encoders[members[1]]=lambda row,i:str(row['_source_counts']['pallet']);encoders[members[2]]=lambda row,i:str(row['_source_counts']['loose'])
            terms=[{'count':ref(c),'unit':u} for c,u in zip(members,['BOX','PALLET','EA'])]
            field('pallet_content','팔레트 내용 수 (EA/PALLET), BOX 입수와 별개이며 회사 표준 대응 항목 없음',semantic_status='operational_only',number_format=nf(p),unit={'kind':'count','dimension':'EA/PALLET'})
            encoders['pallet_content']=lambda row,i:str(row['_source_counts']['pallet_size']);binding(['pallet_content'],[],status='unmapped')
        if members:
            fs={'BOX':factor(pack_col)}
            if n==4:fs['PALLET']=factor('pallet_content','PALLET')
            groups.append(dict(group_id='dispatch-components',kind='quantity_sum',members=members,description=qdesc,basis='EA',terms=terms,factors=fs))
            binding(members,['quantity'],composition=True)
        field(price_basis_col,'견적 금액의 행별 단위 코드 (직접 대응 항목 없음, 계산 문맥으로 사용)',semantic_status='operational_only',unit_codes=unit_codes,factors=factors)
        encoders[price_basis_col]=lambda row,i:source_code(i);binding([price_basis_col],[],status='unmapped')
    field('workflow_queue','거래처 전용 작업 큐이며 회사 표준 항목에 대응하지 않음',semantic_status='operational_only')
    encoders['workflow_queue']=lambda row,i:['합성대기A','합성대기B'][i%2];binding(['workflow_queue'],[],status='unmapped')
    headers=list(meta);rng=random.Random(seed(n,kind,'layout'));rng.shuffle(headers)
    rows=[{col:encoders[col](row,i) for col in headers} for i,row in enumerate(canonical)]
    if len(headers)>20:raise ValueError('Source >20 columns, do not truncate')
    context=dict(synthetic=True,notice=NOTICE,documentation_origin='Authored source-format business definitions, provided equally to all methods; no target IDs',fields=meta,groups=groups)
    if 'target_id' in json.dumps(context):raise ValueError('Target ID in source context')
    if CounterCompat([h for b in bindings for h in b['source_columns']])!=CounterCompat(headers):raise ValueError('Truth source coverage differs')
    return headers,rows,context,dict(synthetic=True,notice=NOTICE,bindings=bindings)


def CounterCompat(values):
    out=defaultdict(int)
    for v in values:out[v]+=1
    return dict(out)


def csv_write(path,headers,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=headers,lineterminator='\n',extrasaction='ignore');w.writeheader();w.writerows(rows)


def main():
    freeze=verify_freeze()
    if NEW_DATA.exists():raise ValueError('Refusing overwrite of holdout')
    tasks=[]
    for n in range(1,5):
        prod=products(n,224+13*n,'source');rprod=products(n,231+13*n,'reference')
        order=orders(n,prod,244+13*n,'source');rorder=orders(n,rprod,255+13*n,'reference')
        for kind,canonical,reference in [('products',prod,rprod),('orders',order,rorder)]:
            tid=f'N{n:02d}_{kind}';inp=NEW_DATA/'model_inputs'/tid;private=NEW_DATA/'private'/tid
            headers,rows,ctx,gold=source_layout(n,kind,canonical);spec=schema(kind)
            csv_write(inp/'source.csv',headers,rows);csv_write(inp/'target_reference.csv',[f['id'] for f in spec['fields']],reference)
            dump(inp/'target_schema.json',spec);dump(inp/'source_context.json',ctx);dump(private/'mapping.json',gold)
            dump(private/'error_injections.json',dict(synthetic=True,notice=NOTICE,errors=[]))
            private.mkdir(parents=True,exist_ok=True)
            (private/'expected_source.jsonl').write_text(''.join(json.dumps({k:v for k,v in row.items() if not k.startswith('_')},ensure_ascii=False)+'\n' for row in canonical),encoding='utf-8')
            src_codes={r['product_code'] for r in canonical};ref_codes={r['product_code'] for r in reference}
            assert src_codes.isdisjoint(ref_codes)
            if kind=='products':assert {r['barcode'] for r in canonical}.isdisjoint({r['barcode'] for r in reference})
            else:
                for sample in (canonical,reference):
                    sums=defaultdict(int)
                    for r in sample:
                        assert r['quantity']*r['unit_price']==r['line_amount']
                        assert r['line_total']==r['line_amount']-r['discount_amount']+r['tax_amount']
                        assert r['tax_amount']==round_won(Decimal(r['line_amount']-r['discount_amount'])*Decimal(str(r['tax_rate'])))
                        sums[r['order_id']]+=r['line_total']
                    assert all(r['order_total']==sums[r['order_id']] for r in sample)
            tasks.append(dict(task_id=tid,rows=len(rows),columns=len(headers),reference_rows=len(reference),structure=PROFILES[n],synthetic=True))
    files=[]
    for path in sorted(p for p in NEW_DATA.rglob('*') if p.is_file()):
        info={'path':path.relative_to(NEW_DATA).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
        path.read_text(encoding='utf-8-sig',errors='strict')
        if path.suffix=='.csv':
            with path.open(encoding='utf-8-sig',newline='') as f:rr=list(csv.reader(f));info.update(rows=len(rr)-1,columns=len(rr[0]))
            assert all(len(row)==info['columns'] for row in rr) and 200<=info['rows']<=500
        files.append(info)
    manifest=dict(synthetic=True,notice=NOTICE,seed=BASE_SEED,candidate_frozen_commit=freeze['commit'],candidate_frozen_at=freeze['at'],
        generated_at=journal.now_iso(),generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        source_type='precision-repaired SAME-family REGRESSION only; not new structural evaluation',
        repair_of_manifest_sha256=hashlib.sha256((OBSERVED_DATA/'manifest.json').read_bytes()).hexdigest(),
        independence_limit='Author knows generic capabilities and selected structures; not author-blind, externally sourced or real-company independent evaluation',
        novelty='NO NEW STRUCTURES: same observed N01-N04, source numerical serialization repaired after evaluation; regression only',
        source_metadata_condition='All methods receive the same natural source descriptions and typed format evidence, no target IDs or truth',
        deliberately_missing_evidence='one purchase-price tax-basis definition per vendor remains missing; mapped bindings not excluded',tasks=tasks,files=files,
        authoring_validation='strict UTF8, CSV width/row range, disjoint identifiers, independent samples, quantity-price/tax/order-total reconciliation pass; no matcher invoked')
    dump(NEW_DATA/'manifest.json',manifest)
    write(ROOT/'B2B_V3_REPAIRED_PROVENANCE.json',{k:v for k,v in manifest.items() if k!='files'},True)
    print(json.dumps({'created_tasks':len(tasks),'synthetic_vendors':4,'candidate_frozen_before_generation':freeze['commit'],'files':len(files)},ensure_ascii=False))


if __name__=='__main__':main()
