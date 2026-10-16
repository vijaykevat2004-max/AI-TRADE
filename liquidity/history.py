"""Persist previously observed closed bars across runner restarts, never fill gaps."""
from datetime import datetime,timedelta
from .kernel import Bar,validate,IST

def retain(store,symbol,frames,now,cfg):
    reset=frames.get('_quality',{}).get('corporate_action_reset')
    repaired=dict(frames);meta={}
    with store.connect() as db:
        for tf,step in [('5m',5),('1d',1440)]:
            cached={b.t:b for b in [Bar(datetime.fromisoformat(t),o,h,l,c,v) for t,o,h,l,c,v in db.execute('SELECT stamp,o,h,l,c,v FROM history WHERE symbol=? AND timeframe=?',(symbol,tf))]}
            accepted=0;invalid=[]
            for b in frames.get(tf,[]):
                try:validate([b],step,now-timedelta(seconds=cfg['finalization_seconds']) if tf=='5m' else now)
                except ValueError:
                    # Never hide a fresh current-session defect, even if a cache exists.
                    if tf=='5m' and b.t.date()==now.astimezone(IST).date():
                        invalid.append(b);cached.pop(b.t,None)
                    continue
                if tf=='1d' and b.t.date()>=now.astimezone(IST).date():continue
                cached[b.t]=b;accepted+=1
            bars=sorted(cached.values(),key=lambda b:b.t)
            if reset:bars=[b for b in bars if str(b.t.date())>=reset] if tf=='5m' else [b for b in bars if str(b.t.date())>reset]
            if tf=='5m':
                dates=sorted({b.t.date() for b in bars})[-3:]
                bars=[b for b in bars if b.t.date() in dates]
            else:bars=bars[-cfg['daily_lookback']:]
            db.execute('DELETE FROM history WHERE symbol=? AND timeframe=?',(symbol,tf))
            db.executemany('INSERT INTO history VALUES(?,?,?,?,?,?,?,?,?)',[(symbol,tf,b.t.isoformat(),b.o,b.h,b.l,b.c,b.v,now.isoformat()) for b in bars])
            output={b.t:b for b in bars};output.update({b.t:b for b in invalid})
            repaired[tf]=sorted(output.values(),key=lambda b:b.t)
            meta[tf]=dict(retained=len(bars),observed_this_fetch=accepted,current_defects=len(invalid))
    # Any residual prior gap still resets warmup. Persistence is not interpolation.
    from .feed import bounded_context
    repaired['5m'],context=bounded_context(repaired['5m'],now,cfg)
    repaired['_quality']=dict(frames.get('_quality',{}),**context,persistent_history=meta)
    return repaired
