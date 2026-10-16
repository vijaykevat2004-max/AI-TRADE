"""Persist previously observed closed bars across runner restarts, never fill gaps."""
from datetime import datetime,timedelta
import json
from .kernel import Bar,validate,IST

def retain(store,symbol,frames,now,cfg):
    reset=frames.get('_quality',{}).get('corporate_action_reset')
    repaired=dict(frames);meta={}
    with store.connect() as db:
        for tf,step in [('5m',5),('1d',1440)]:
            cached={b.t:b for b in [Bar(datetime.fromisoformat(t),o,h,l,c,v) for t,o,h,l,c,v in db.execute('SELECT stamp,o,h,l,c,v FROM history WHERE symbol=? AND timeframe=?',(symbol,tf))]}
            # A new dividend can revise every adjustment factor. Never combine an
            # older price basis with today's complete provider-adjusted snapshot.
            adjusted=frames.get('_quality',{}).get('daily_price_basis')=='PROVIDER_ADJUSTED'
            # Intraday cached snapshots also use dated factors. When they change,
            # reset that symbol's cache instead of mixing incompatible bases.
            if adjusted:
                basis=frames.get('_quality',{}).get('adjustment_factors',{})
                identity=json.dumps(basis,sort_keys=True)
                db.execute('CREATE TABLE IF NOT EXISTS history_basis(symbol TEXT PRIMARY KEY,identity TEXT)')
                old=db.execute('SELECT identity FROM history_basis WHERE symbol=?',(symbol,)).fetchone()
                try:previous_basis=json.loads(old[0]) if old else None
                except ValueError:previous_basis=None
                changed=previous_basis is None or any(day in basis and abs(float(factor)-float(basis[day]))>1e-10 for day,factor in (previous_basis or {}).items())
                if changed:
                    db.execute('DELETE FROM history WHERE symbol=?',(symbol,));cached={}
                db.execute('INSERT OR REPLACE INTO history_basis VALUES(?,?)',(symbol,identity))
                if tf=='1d':cached={}
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
            if reset and not (tf=='1d' and adjusted):bars=[b for b in bars if str(b.t.date())>=reset] if tf=='5m' else [b for b in bars if str(b.t.date())>reset]
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
