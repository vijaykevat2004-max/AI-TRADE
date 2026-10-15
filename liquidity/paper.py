"""Forward-only paper outcomes. No broker, no fills before signal discovery."""
from datetime import datetime,timedelta,timezone
import json,math,re
from .kernel import IST,validate

TERMINAL={'CLOSED','AMBIGUOUS','MISSED_SETUP'}

def register(store,signal):
    if signal.get('decision') not in ('BUY','SELL') or signal.get('strategy_id')!='jadecap_nse_liquidity_v1':return
    safe={k:v for k,v in signal.items() if k not in ('evidence','evidence_canonical','structure_15m_pivots')}
    record=dict(id=signal['id'],symbol=signal['symbol'],signal=safe,status='ENTRY_PENDING',result=None,is_paper=True,execution_enabled=False,entry_policy='NEXT_FULL_BAR_OPEN_AFTER_DISCOVERY',evidence_ref=signal.get('evidence_ref'))
    with store.connect() as db:db.execute('INSERT OR IGNORE INTO paper(id,symbol,record) VALUES(?,?,?)',(record['id'],record['symbol'],json.dumps(record,default=str)))

def records(store,symbol=None):
    with store.connect() as db:
        rows=db.execute('SELECT record FROM paper'+(' WHERE symbol=?' if symbol else ''),(symbol,) if symbol else ())
        return [json.loads(r[0]) for r in rows]

def evaluate_paper(record,bars,as_of,cfg):
    if record['status'] in TERMINAL:return record
    s=record['signal'];r=dict(record);side=1 if s['decision']=='BUY' else -1
    step=cfg.get('bar_minutes',5)
    discovered=datetime.fromisoformat(s['earliest_actionable_time'])
    expected=datetime.fromtimestamp(math.ceil(discovered.timestamp()/(step*60))*step*60,tz=discovered.tzinfo)
    day=discovered.astimezone(IST).date()
    future=[b for b in bars if b.t>=expected and b.t.astimezone(IST).date()==day and b.t+timedelta(minutes=step,seconds=cfg['finalization_seconds'])<=as_of]
    if not future:
        if as_of.astimezone(IST).date()>day:r.update(status='DATA_MISSING',reason='MISSING_SESSION_OUTCOME_BARS')
        return r
    try:
        validate(future[:1],step,as_of-timedelta(seconds=cfg['finalization_seconds']))
        if future[0].t!=expected:raise ValueError('MISSING_FIRST_ACTIONABLE_BAR')
    except ValueError as e:return dict(r,status='DATA_MISSING',reason=str(e))
    entry=future[0].o;stop=s['stop'];target=s['targets'][0]
    if expected.astimezone(IST).strftime('%H:%M')>cfg['entry_window'][1] or side*(entry-stop)<=0 or side*(target-entry)<=0:
        return dict(r,status='MISSED_SETUP',reason='ENTRY_TOO_LATE_OR_LEVEL_ALREADY_PASSED',updated_at=as_of.isoformat())
    if abs(entry-s['entry_reference'])>cfg.get('paper_max_chase_r',.5)*abs(s['entry_reference']-stop):
        return dict(r,status='MISSED_SETUP',reason='PAPER_ENTRY_CHASE_LIMIT',updated_at=as_of.isoformat())
    r.update(status='OPEN',paper_entry=entry,paper_entry_at=expected.isoformat(),updated_at=as_of.isoformat())
    for index,b in enumerate(future):
        try:validate(future[max(0,index-1):index+1],step,as_of-timedelta(seconds=cfg['finalization_seconds']))
        except ValueError as e:return dict(r,status='DATA_MISSING',reason=str(e))
        hit_stop=b.l<=stop if side==1 else b.h>=stop
        hit_target=b.h>=target if side==1 else b.l<=target
        if hit_stop and hit_target:return dict(r,status='AMBIGUOUS',reason='BOTH_LEVELS_WITHIN_ONE_BAR',exit_bar=b.t.isoformat(),result=None)
        reason=None;exit_price=None
        if hit_stop:reason='STOP';exit_price=min(stop,b.o) if side==1 else max(stop,b.o)
        elif hit_target:reason='TARGET';exit_price=target
        elif (b.t+timedelta(minutes=step)).astimezone(IST).strftime('%H:%M')>=cfg['expiry']:reason='TIMEOUT';exit_price=b.c
        if reason:
            cost=entry*cfg['round_trip_cost_bps']/10000+2*cfg['slippage_ticks']*cfg['tick_size']
            gross=side*(exit_price-entry);net=gross-cost
            return dict(r,status='CLOSED',exit_reason=reason,exit_reference=exit_price,exit_bar=b.t.isoformat(),result='POSITIVE' if net>0 else 'NEGATIVE' if net<0 else 'FLAT',gross_points=gross,estimated_cost_points=cost,net_points=net,net_r=net/(abs(entry-stop)+cost),target_hit=reason=='TARGET',costs_are_assumptions=True)
    return r

def update_symbol(store,symbol,bars,as_of,cfg):
    for record in records(store,symbol):
        if record['status'] in TERMINAL:continue
        updated=evaluate_paper(record,bars,as_of,cfg)
        with store.connect() as db:db.execute('UPDATE paper SET record=? WHERE id=?',(json.dumps(updated,default=str),record['id']))

def summary(store):
    all_records=records(store);closed=[r for r in all_records if r['status']=='CLOSED'];positive=sum(r['result']=='POSITIVE' for r in closed);negative=sum(r['result']=='NEGATIVE' for r in closed)
    return dict(total=len(all_records),positive=positive,negative=negative,flat=sum(r['result']=='FLAT' for r in closed),pending=sum(r['status'] in ('OPEN','ENTRY_PENDING') for r in all_records),data_missing=sum(r['status']=='DATA_MISSING' for r in all_records),ambiguous=sum(r['status']=='AMBIGUOUS' for r in all_records),missed=sum(r['status']=='MISSED_SETUP' for r in all_records),target_hits=sum(r.get('exit_reason')=='TARGET' for r in closed),stop_hits=sum(r.get('exit_reason')=='STOP' for r in closed),timeouts=sum(r.get('exit_reason')=='TIMEOUT' for r in closed),positive_rate=positive/len(closed) if closed else None,expectancy_net_r=sum(r['net_r'] for r in closed)/len(closed) if closed else None,method='Paper only; next observed full-bar open after discovery; assumed costs; ambiguous and missing data excluded from positive rate')

def sync_journal(store,github,issues):
    """Per-day paged issue ledger survives cache eviction; no raw OHLCV upload."""
    groups={}
    for r in sorted(records(store),key=lambda x:x['id']):groups.setdefault(r['signal']['session_date_ist'],[]).append(r)
    for day,rs in groups.items():
        for start in range(0,len(rs),20):
            title=f'[NIFTY paper journal] {day} / {start//20+1}'
            body='Automatic paper lifecycle; no broker orders.\n\n```json\n'+json.dumps(dict(strategy_id='jadecap_nse_liquidity_v1',records=rs[start:start+20]),indent=2)+'\n```'
            existing=next((i for i in issues if i['title']==title),None)
            if existing:
                if existing.get('body')!=body:github.api('/issues/'+str(existing['number']),dict(body=body),'PATCH')
            else:github.api('/issues',dict(title=title,body=body))

def restore_journal(store,issues):
    for issue in issues:
        if not issue['title'].startswith('[NIFTY paper journal] ') or issue.get('user',{}).get('login')!='github-actions[bot]':continue
        match=re.search(r'```json\s*([\s\S]*?)```',issue.get('body') or '')
        try:data=json.loads(match[1]) if match else {}
        except (ValueError,TypeError):continue
        if data.get('strategy_id')!='jadecap_nse_liquidity_v1':continue
        for r in data.get('records',[]):
            if not re.fullmatch('[a-f0-9]{64}',str(r.get('id',''))) or r.get('execution_enabled') is not False:continue
            if not re.fullmatch('[A-Z0-9&-]{1,24}',str(r.get('symbol',''))):continue
            with store.connect() as db:db.execute('INSERT OR IGNORE INTO paper VALUES(?,?,?)',(r['id'],r['symbol'],json.dumps(r)))
