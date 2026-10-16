"""Observed one-minute aggregation only. No interpolation or synthetic volume."""
import math
from datetime import timedelta
from .kernel import Bar,IST,validate

def reconcile(primary,minutes,now,cfg):
    groups={}
    for b in minutes:
        t=b.t.astimezone(IST)
        if not (555<=t.hour*60+t.minute<930) or t.second:continue
        start=t-timedelta(minutes=(t.hour*60+t.minute-555)%5)
        groups.setdefault(start,[]).append(b)
    aggregates={}
    for start,rows in groups.items():
        rows=sorted(rows,key=lambda b:b.t)
        if [b.t for b in rows]!=[start+timedelta(minutes=i) for i in range(5)]:continue
        if start+timedelta(minutes=5,seconds=cfg['finalization_seconds'])>now:continue
        if any(not all(math.isfinite(x) for x in (b.o,b.h,b.l,b.c,b.v)) or b.v<0 or min(b.o,b.h,b.l,b.c)<=0 or b.l>min(b.o,b.c) or b.h<max(b.o,b.c) for b in rows):continue
        bar=Bar(start,rows[0].o,max(b.h for b in rows),min(b.l for b in rows),rows[-1].c,sum(b.v for b in rows))
        if bar.v>0:aggregates[start]=bar
    merged={b.t:b for b in primary};repairs=[];conflicts=[]
    for stamp,b in aggregates.items():
        old=merged.get(stamp)
        if old:
            try:validate([old],5,now-timedelta(seconds=cfg['finalization_seconds']));continue
            except ValueError:pass
            # Conflicting prices cannot be silently combined with another interval.
            if any(abs(x-y)>cfg['tick_size'] for x,y in zip((old.o,old.h,old.l,old.c),(b.o,b.h,b.l,b.c))):
                conflicts.append(stamp.isoformat());continue
        merged[stamp]=b;repairs.append(stamp.isoformat())
    return sorted(merged.values(),key=lambda b:b.t),dict(method='OBSERVED_1M_TO_5M_RECONCILIATION',repaired_count=len(repairs),repaired_bars=repairs,conflicting_bars=conflicts,volume_note='Sum of reported one-minute volumes; provider zero-volume minutes remain source uncertainty',synthetic_bars=False)

def bounded_context(bars,now,cfg):
    """Reset history after a defective PRIOR-session prefix. Never trim today's faults.

    This explicitly changes available pivot context and may require fresh warmup.
    No signal can use dropped bars; current opening/session continuity stays required.
    """
    today=now.astimezone(IST).date();cut=0
    if cfg.get('intraday_context_policy')=='LATEST_CLEAN_PRIOR_SEGMENT':
        current=[b for b in bars if b.t.astimezone(IST).date()==today]
        chunks=[];chunk=[]
        for b in [b for b in bars if b.t.astimezone(IST).date()<today]:
            try:validate([b],5,now-timedelta(seconds=cfg['finalization_seconds']))
            except ValueError:
                if chunk:chunks.append(chunk)
                chunk=[];continue
            if chunk and (b.t.date()!=chunk[-1].t.date() or b.t-chunk[-1].t!=timedelta(minutes=5)):
                chunks.append(chunk);chunk=[]
            chunk.append(b)
        if chunk:chunks.append(chunk)
        eligible=[c for c in chunks if len(c)>=20]
        seed=eligible[-1] if eligible else []
        selected=seed+current
        return selected,dict(context_policy='LATEST_CLEAN_PRIOR_SEGMENT_PLUS_FULL_CURRENT_SESSION',excluded_prior_bars=len(bars)-len(selected),context_start=selected[0].t.isoformat() if selected else None,seed_bars=len(seed),seed_end=seed[-1].t.isoformat() if seed else None,current_session_faults_removed=False,missing_bars_filled=False)
    for i,b in enumerate(bars):
        if b.t.astimezone(IST).date()>=today:break
        try:validate([b],5,now-timedelta(seconds=cfg['finalization_seconds']))
        except ValueError:cut=i+1
        if i and b.t.date()==bars[i-1].t.date() and b.t-bars[i-1].t!=timedelta(minutes=5):cut=max(cut,i)
    return bars[cut:],dict(context_policy='RESET_AFTER_LAST_PRIOR_SESSION_DEFECT',excluded_prior_bars=cut,context_start=bars[cut].t.isoformat() if cut<len(bars) else None,current_session_faults_removed=False)
