"""Official uncompressed NSE daily records for missing provider dates."""
import csv,io,hashlib,threading,math
from datetime import datetime
from .kernel import IST,Bar,validate
_cache={};_lock=threading.Lock()

def official_day(day,symbol,now):
    from monitor import request
    url='https://archives.nseindia.com/products/content/sec_bhavdata_full_'+day.strftime('%d%m%Y')+'.csv'
    with _lock:
        if day not in _cache:
            raw=request(url)
            rows=[{k.strip():v.strip() for k,v in r.items()} for r in csv.DictReader(io.StringIO(raw))]
            _cache[day]=(rows,hashlib.sha256(raw.encode()).hexdigest())
        rows,sha=_cache[day]
    matches=[r for r in rows if r.get('SYMBOL')==symbol and r.get('SERIES')=='EQ']
    if len(matches)!=1:raise ValueError('OFFICIAL_DAILY_SYMBOL_NOT_UNIQUE')
    row=matches[0]
    if datetime.strptime(row['DATE1'],'%d-%b-%Y').date()!=day:raise ValueError('OFFICIAL_DAILY_DATE_MISMATCH')
    bar=Bar(datetime.combine(day,datetime.min.time(),tzinfo=IST),*[float(row[k]) for k in ('OPEN_PRICE','HIGH_PRICE','LOW_PRICE','CLOSE_PRICE','TTL_TRD_QNTY')])
    validate([bar],1440,now)
    return bar,float(row['PREV_CLOSE']),dict(source=url,csv_sha256=sha,day=str(day),symbol=symbol)

def recover(frame,intraday,symbol,now,cfg):
    """No inferred OHLC. Adjustment factor requires agreeing observed brackets
    and official PREV_CLOSE agreeing with the provider's prior raw close."""
    f=frame.copy();evidence=[]
    dates=sorted({s.date() for s in intraday.index})[-3:]
    for day in dates:
        if day>=now.astimezone(IST).date():continue
        rows=f[[s.date()==day for s in f.index]]
        if len(rows)==1 and all(math.isfinite(float(rows.iloc[0][k])) and float(rows.iloc[0][k])>0 for k in ('Open','High','Low','Close','Volume','Adj Close')):continue
        valid=[(s,r) for s,r in f.sort_index().iterrows() if s.date()<=now.date() and all(math.isfinite(float(r[k])) and float(r[k])>0 for k in ('Close','Adj Close'))]
        left=[(s,r) for s,r in valid if s.date()<day];right=[(s,r) for s,r in valid if s.date()>day]
        if not left or not right:raise ValueError('DAILY_REPAIR_ADJUSTMENT_BRACKET_MISSING')
        ls,lr=left[-1];rs,rr=right[0]
        a=float(lr['Adj Close']/lr['Close']);b=float(rr['Adj Close']/rr['Close'])
        if abs(a-b)>1e-8:raise ValueError('DAILY_REPAIR_ADJUSTMENT_BRACKETS_CONFLICT')
        bar,previous,proof=official_day(day,symbol,now)
        if abs(previous-float(lr['Close']))>cfg['tick_size']:raise ValueError('DAILY_REPAIR_PREVIOUS_CLOSE_CONFLICT')
        for s in rows.index:f=f.drop(s)
        values=dict(Open=bar.o,High=bar.h,Low=bar.l,Close=bar.c,Volume=bar.v,**{'Adj Close':bar.c*a,'Dividends':0,'Stock Splits':0})
        for key,value in values.items():f.loc[bar.t,key]=value
        evidence.append(dict(proof,adjustment_factor=a,adjustment_basis='AGREEING_OBSERVED_BRACKETS_WITH_OFFICIAL_PREVIOUS_CLOSE_CHECK',left_date=str(ls.date()),right_date=str(rs.date())))
    return f.sort_index(),evidence
