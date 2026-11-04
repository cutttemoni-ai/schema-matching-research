from schema_match.synthetic_refiner import refine,make_conversion
from schema_match.synthetic_transforms import apply


def wire(columns,fields,rows):
    return {'source_columns':[{'id':i,'name':n} for i,n in columns],
        'target_fields':[{'id':i,'name':i,'data_type':t,'profile':{'features':{}}} for i,t,u in fields],
        'standard_metadata':{'fields':[{'id':i,'label':i,'unit':u} for i,t,u in fields]},'observed_rows':rows}


def test_constant_numeric_unknown_stays_review_not_forced_no_match():
    w=wire([('s','opaque')],[('price','number','KRW')],[{'s':'1000'}]*12)
    r={'raw_recommendations':[{'source_id':'s','target_id':None,'status':'no_match','reason':'Unknown constant'}]}
    assert refine(w,r)[0]['status']=='needs_review'


def test_explicit_box_and_pack_operand_without_hidden_constant():
    w=wire([('q','ordered boxes'),('p','pack count'),('u','UOM')],
        [('quantity','integer','EA'),('pack_size','integer','EA/BOX'),('quantity_unit','string','EA')],
        [{'q':'2','p':'12','u':'BOX'}]*12)
    raw=[{'source_id':'q','target_id':'quantity','status':'needs_review','reason':'BOX unit conversion required'},
         {'source_id':'p','target_id':'pack_size','status':'matched','reason':'pack size'},
         {'source_id':'u','target_id':'quantity_unit','status':'matched','reason':'unit'}]
    r=refine(w,{'raw_recommendations':raw})
    c=next(x for x in r if x['source_ids']==['q'])['conversions'][0]
    assert c['source_ids']==['q','p'] and apply(c,w['observed_rows'][0])==24


def test_ambiguous_month_day_not_assumed():
    w=wire([('s','date')],[('order_date','date',None)],[{'s':'01/02/2025'},{'s':'02/03/2025'}])
    c=make_conversion(w,{'source_ids':['s']},'order_date',[])
    assert c['status']=='needs_review'


def test_independent_aliases_not_merged_into_one_relation():
    w=wire([('a','price1'),('b','price2')],[('sale_price','number','KRW/EA')],[{'a':'1200','b':'1200'}]*12)
    raw=[{'source_id':s,'target_id':'sale_price','status':'matched','reason':'price'} for s in ('a','b')]
    result=refine(w,{'raw_recommendations':raw})
    assert len(result)==2 and all(len(r['source_ids'])==1 and r['status']=='matched' for r in result)


def test_unknown_composite_does_not_invent_roles():
    w=wire([('s','opaque')],[('thing','string',None),('other','string',None)],[{'s':'abc|xyz'}]*12)
    raw=[{'source_id':'s','target_id':None,'status':'needs_review','reason':'combined unknown fields'}]
    result=refine(w,{'raw_recommendations':raw})
    assert result[0]['status']=='needs_review' and result[0]['target_ids']==[]
