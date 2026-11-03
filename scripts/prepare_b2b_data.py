"""Offline corpus/answer separation. Never creates a model client or runs inference."""
import argparse,csv,io,json,sys
from pathlib import Path
from hashlib import sha256
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.records import now_iso
from schema_match.research_data import read_table
from schema_match import gemini_main30 as old

ROOT=Path(__file__).resolve().parents[1]

def csv_bytes(headers,rows):
    out=io.StringIO(newline='');w=csv.writer(out);w.writerow(headers);w.writerows(rows)
    return out.getvalue().encode('utf-8-sig')

def prepare(history):
    base=history/'datasets/b2b-v1';out=history/'research-artifacts/b2b-v1'
    raw=base/'raw';derived=base/'derived';derived.mkdir(parents=True,exist_ok=True)
    manifest={'version':'b2b-corpus-v1','at':now_iso(),'actual_private_company_files':0,'new_model_calls':0,
      'source_families':[],'files':[],'truth_review':'Assistant-authored provisional mappings from field documentation; no human business review.',
      'splitting':'All derivatives/header variants/row subsets from one root family stay in one split; no random row split.',
      'legacy_research':'WDC/Korean public/Valentine/temporal/semantic studies preserved as reference; not B2B validation.'}
    manifest['source_families']=[
      {'id':'uci-online-retail-root','split':'development','origin':'public_real_transactions','source':'https://archive.ics.uci.edu/dataset/352/online+retail',
       'citation':'Chen, D. (2015). Online Retail. DOI10.24432/C5BW33','license':'CC BY 4.0','version':'UCI352, 2010-12-01..2011-12-09; acquisition snapshot',
       'limitations':'One historical UK retailer; many wholesalers, not a verified current B2B partner template. Invoice event is not automatically an order event.'},
      {'id':'openfoodfacts-root','split':'evaluation','origin':'public_crowdsourced_catalog','source':'https://world.openfoodfacts.org/',
       'license':'ODbL-1.0 database; DbCL individual contents; no images acquired','version':'APIv2 read-only30-product snapshot; live catalog not fixed release',
       'limitations':'One catalog family; popularity-ranked convenience sample, not a supplier template. Not manually checked. No independent order holdout.'},
      {'id':'legacy-handwritten-demo','split':'development','origin':'authored_synthetic_and_header_subset_variants','source':'repository examples/normal.csv,abbreviated.csv,extra_columns.csv,review_source.csv',
       'license':'Project-authored fixtures','version':'existing frozen example bytes','limitations':'Previously developed/tested. Header/row derivatives are not separate real companies.'},
      {'id':'b2b-handwritten-demo-v1','split':'development','origin':'authored_synthetic','source':'examples/b2b_products.csv and b2b_orders.csv',
       'license':'Project-authored fixtures','version':'b2b-fixtures-v1','limitations':'Two task shapes from one author family; not independent real suppliers.'}]
    uci_headers=['InvoiceNo','StockCode','Description','Quantity','InvoiceDate','UnitPrice']
    # First1000 physical source records, not selected by matcher scores; preserve cancellation/negative/missing data.
    with (raw/'uci-online-retail.csv').open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);assert set(uci_headers+['CustomerID','Country'])<=set(reader.fieldnames)
        rows=[]
        for i,row in enumerate(reader):
            if i>=1000:break
            rows.append([row[k] for k in uci_headers])
    old.atomic(derived/'uci-orders-first1000.csv',csv_bytes(uci_headers,rows),True)
    products=json.loads((raw/'off-products.json').read_bytes())['products']
    off_headers=['code','product_name','quantity','brands','categories','packaging']
    old.atomic(derived/'off-catalog-first30.csv',csv_bytes(off_headers,[[str(p.get(k,'')) for k in off_headers] for p in products]),True)
    specs=[('uci-orders-first1000','uci-online-retail-root','order_lines_v1',derived/'uci-orders-first1000.csv',
        {'InvoiceNo':('order_number','ambiguous','Invoice ID is not necessarily purchase order ID.'),
         'InvoiceDate':('order_date','ambiguous','Invoice timestamp is not necessarily order reception date; date-only conversion is separate.'),
         'StockCode':('product_code','defined','UCI dictionary: distinct product item code; not barcode.'),
         'Description':('product_name','defined','UCI dictionary: product name.'),
         'Quantity':('quantity','defined','UCI dictionary: quantity per transaction item; preserve returns.'),
         'UnitPrice':('unit_price','defined','UCI dictionary: transaction price per unit in sterling. Currency not inferred as a new source column.')}),
        ('off-catalog-first30','openfoodfacts-root','product_catalog_v1',derived/'off-catalog-first30.csv',
         {'code':('barcode','defined','Official field dictionary calls code a product barcode/internal reserved identifier; preserve exact string, no SKU equivalence.'),
          'product_name':('product_name','defined','Official field dictionary: product name.'),
          'quantity':('specification','defined','Official dictionary: package quantity AND unit; content specification, not order count or sales unit.'),
          'brands':('brand','defined','Official brands field; not manufacturer or supplier.'),
          'categories':(None,'defined','No category standard field supplied.'),
          'packaging':(None,'defined','Packaging shape/material is not a sales counting unit. No supplied corresponding standard field.')})]
    # Include clearly marked synthetic schemas with author-defined truth, not real-company claims.
    fixture_maps={
      'b2b_products.csv':('product_catalog_v1',{'거래처상품코드':'product_code','품명':'product_name','선택옵션':'option','제품규격':'specification','판매단위':'sales_unit','판매가':'sale_price','매입가':'purchase_price','바코드':'barcode','통화':'currency','브랜드':'brand','메모':None}),
      'b2b_orders.csv':('order_lines_v1',{'발주번호':'order_number','주문접수일':'order_date','거래처상품코드':'product_code','품명':'product_name','선택옵션':'option','발주수량':'quantity','거래단가':'unit_price','행금액':'line_amount','주문전체금액':'order_total','통화':'currency','내부메모':None})}
    for filename,(standard,mapping) in fixture_maps.items():
        specs.append((filename[:-4],'b2b-handwritten-demo-v1',standard,ROOT/'examples'/filename,
            {k:(v,'defined','Synthetic author-defined field; not human-verified real data.') for k,v in mapping.items()}))
    tasks=[];answers=[]
    for file_id,family,standard,path,mapping in specs:
        table=read_table(path);schema=json.loads((ROOT/'schemas'/f'{standard}.json').read_bytes())
        split=next(f['split'] for f in manifest['source_families'] if f['id']==family)
        manifest['files'].append({'file_id':file_id,'family_id':family,'split':split,'standard_id':standard,
          'path':str(path.relative_to(history)) if path.is_relative_to(history) else 'examples/'+path.name,
          'sha256':old.filehash(path),'rows':len(table.rows),'columns':len(table.headers),
          'raw_values_publicly_committed':False if family in ('uci-online-retail-root','openfoodfacts-root') else True,
          'privacy':'UCI CustomerID and Country excluded from derivative; originals preserved privately.' if file_id.startswith('uci') else 'Only product attributes; no contributor/contact identifiers requested.'})
        for i,header in enumerate(table.headers):
            expected,status,basis=mapping[header];identifier=old.digest(['b2b-corpus-v1',file_id,i])[:32]
            tasks.append({'id':identifier,'file_id':file_id,'family_id':family,'split':split,'source_index':i,
              'source_name':header,'standard_id':standard,'candidate_ids':[f['id'] for f in schema['fields']]})
            answers.append({'id':identifier,'file_id':file_id,'truth_status':status,'expected_target_id':expected,
                'basis':basis,'human_reviewed':False})
    # Older example families remain in the ledger; never reclassify them as held out.
    for filename in ('normal.csv','abbreviated.csv','extra_columns.csv','review_source.csv'):
        path=ROOT/'examples'/filename
        manifest['files'].append({'file_id':'legacy-'+filename,'family_id':'legacy-handwritten-demo','split':'development',
            'path':'examples/'+filename,'sha256':old.filehash(path),'rows':len(read_table(path).rows),'derived_header_or_subset':filename!='normal.csv','selected_for_new_evaluation':False})
    manifest['raw_hashes']={p.name:old.filehash(p) for p in raw.iterdir() if p.is_file()}
    manifest['task_count']=len(tasks);manifest['ambiguous_truth_columns']=sum(a['truth_status']!='defined' for a in answers)
    manifest['no_match_columns']=sum(a['truth_status']=='defined' and a['expected_target_id'] is None for a in answers)
    plan={'version':'b2b-data-freeze-v1','at':now_iso(),'tasks':tasks,
      'schemas':{name:old.filehash(ROOT/'schemas'/f'{name}.json') for name in ('product_catalog_v1','order_lines_v1')},
      'files':{f['file_id']:f['sha256'] for f in manifest['files']},
      'scoring':'Full planned denominator; exact target+matched, or true none+no_match. Review/API/output/unexecuted remain failures. Unknown truth not relabeled; unresolved truth prevents certification.',
      'human_review_required':True,'model_calls':0}
    old.atomic(out/'manifest.json',manifest,True);old.atomic(out/'tasks.json',plan,True)
    old.atomic(out/'answers.json',{'answers':answers,'human_reviewed':False},True)
    old.atomic(out/'seal.json',{'tasks_sha256':old.filehash(out/'tasks.json'),'answers_sha256':old.filehash(out/'answers.json'),'manifest_sha256':old.filehash(out/'manifest.json')},True)
    # Public manifest contains schema names/counts/hashes only, never source records or customer IDs.
    old.atomic(ROOT/'B2B_DATA_MANIFEST.json',manifest,True)
    old.atomic(ROOT/'B2B_TASKS.json',plan,True)
    old.atomic(ROOT/'B2B_PROVISIONAL_ANSWERS.json',{'answers':answers,'human_reviewed':False},True)
    print(json.dumps({'files':len(manifest['files']),'frozen_columns':len(tasks),'ambiguous':manifest['ambiguous_truth_columns'],'no_match':manifest['no_match_columns'],'new_model_calls':0}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--history-root',type=Path,required=True);a=p.parse_args();prepare(a.history_root.resolve())
