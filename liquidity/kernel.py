"""Causal pure kernel. All engineering thresholds are proposed, not source rules."""
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import hashlib
import json
import math

IST = ZoneInfo('Asia/Kolkata')

@dataclass(frozen=True)
class Bar:
    t: datetime  # timezone-aware OPEN time
    o: float
    h: float
    l: float
    c: float
    v: float

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, allow_nan=False).encode()).hexdigest()

def validate(bars, minutes, as_of):
    last = None
    for b in bars:
        if b.t.tzinfo is None or b.t + timedelta(minutes=minutes) > as_of:
            raise ValueError('UNCONFIRMED_OR_NAIVE_BAR')
        if last and b.t <= last.t:
            raise ValueError('DUPLICATE_OR_UNSORTED_BAR')
        if not all(math.isfinite(x) for x in [b.o,b.h,b.l,b.c,b.v]) or min(b.o,b.h,b.l,b.c) <= 0 or b.v <= 0 or b.l > min(b.o,b.c) or b.h < max(b.o,b.c):
            raise ValueError('INVALID_OHLCV')
        if minutes < 1440:
            t = b.t.astimezone(IST)
            minute = t.hour*60+t.minute
            if not (555 <= minute < 930) or (minute-555)%minutes or t.second:
                raise ValueError('OFF_GRID_BAR')
            if last and last.t.astimezone(IST).date() == t.date() and b.t-last.t != timedelta(minutes=minutes):
                raise ValueError('GAP_IN_SESSION')
        last = b

def pivots(bars, left=2, right=2):
    """Return only pivots whose right-side bars already exist in the input prefix."""
    out=[]
    for i in range(left, len(bars)-right):
        others=bars[i-left:i]+bars[i+1:i+right+1]
        if all(bars[i].h > b.h for b in others):
            out.append(dict(kind='HIGH', price=bars[i].h, index=i, confirmation_bar_open=bars[i+right].t.isoformat()))
        if all(bars[i].l < b.l for b in others):
            out.append(dict(kind='LOW', price=bars[i].l, index=i, confirmation_bar_open=bars[i+right].t.isoformat()))
    return out

def bias(daily, config):
    ps=pivots(daily,config['pivot_left'],config['pivot_right'])
    highs=[p for p in ps if p['kind']=='HIGH']; lows=[p for p in ps if p['kind']=='LOW']
    if len(daily)<20 or not highs or not lows: return 'NEUTRAL'
    return 'BULLISH' if daily[-1].c>highs[-1]['price'] else 'BEARISH' if daily[-1].c<lows[-1]['price'] else 'NEUTRAL'

def fvg(bars, minimum):
    if len(bars)<3: return None
    a,_,c=bars[-3:]
    if c.l-a.h>=minimum: return dict(side='BUY',zone=[a.h,c.l],kind='FVG')
    if a.l-c.h>=minimum: return dict(side='SELL',zone=[c.h,a.l],kind='FVG')
    return None

def aggregate15(bars):
    groups={}
    for b in bars:
        t=b.t.astimezone(IST)
        start=t-timedelta(minutes=(t.hour*60+t.minute-555)%15)
        groups.setdefault(start,[]).append(b)
    return [Bar(t,g[0].o,max(b.h for b in g),min(b.l for b in g),g[-1].c,sum(b.v for b in g)) for t,g in groups.items() if len(g)==3 and [b.t for b in g]==[t+timedelta(minutes=i) for i in (0,5,10)]]

def levels(prior, daily, config):
    result=[dict(kind='PDH',side='HIGH',price=daily[-1].h),dict(kind='PDL',side='LOW',price=daily[-1].l)]
    ps=pivots(prior,config['pivot_left'],config['pivot_right'])
    for p in ps[-12:]: result.append(dict(kind='PIVOT_'+p['kind'],side=p['kind'],price=p['price']))
    for side in ('HIGH','LOW'):
        pool=[p for p in ps if p['kind']==side]
        if len(pool)>=2 and abs(pool[-1]['price']-pool[-2]['price'])<=config['equal_tolerance_ticks']*config['tick_size']:
            result.append(dict(kind='EQUAL_'+side,side=side,price=pool[-1]['price']))
    today=[b for b in prior if b.t.astimezone(IST).date()==prior[-1].t.astimezone(IST).date()] if prior else []
    opening=[b for b in today if '09:15'<=b.t.astimezone(IST).strftime('%H:%M')<'09:30']
    if len(opening)==3:
        result.extend([dict(kind='ORH',side='HIGH',price=max(b.h for b in opening)),dict(kind='ORL',side='LOW',price=min(b.l for b in opening))])
    return result

def risk(side, entry, extreme, references, atr, cfg):
    sign=1 if side=='BUY' else -1
    stop=extreme-sign*cfg['stop_buffer_ticks']*cfg['tick_size']
    targets=sorted((r['price'] for r in references if r['side']==('HIGH' if sign==1 else 'LOW') and sign*(r['price']-entry)>0),reverse=sign<0)
    risk_distance=sign*(entry-stop)
    if risk_distance<=0 or not targets: return None,'NO_OPPOSITE_TARGET'
    target=targets[0]; reward=sign*(target-entry)
    cost=entry*cfg['round_trip_cost_bps']/10000+2*cfg['slippage_ticks']*cfg['tick_size']
    net=(reward-cost)/(risk_distance+cost)
    if net<cfg['min_net_rr']: return None,'NET_RR_TOO_LOW'
    return dict(entry_reference=entry,stop=stop,targets=[target],gross_rr=reward/risk_distance,estimated_net_rr=net),'RISK_VALID'

def evaluate(symbol: str, as_of: datetime, confirmed_bars: dict, config: dict) -> dict:
    """No network, persistence, random, LLM, current clock, or execution side effects."""
    d=dict(symbol=symbol,strategy_id=config['strategy_id'],version=config['strategy_version'],decision='NO_TRADE',status='WARMUP',reason_codes=[],is_paper=True,execution_enabled=False,source_mode=config['source_mode'],data_delay_sec=None)
    def reject(status,reason):
        d.update(status=status,reason_codes=[reason]);return d
    if as_of.tzinfo is None: return reject('UNAVAILABLE','NAIVE_AS_OF')
    bars=confirmed_bars.get('5m',[])
    daily=[b for b in confirmed_bars.get('1d',[]) if b.t.astimezone(IST).date()<as_of.astimezone(IST).date()]
    try:
        validate(bars,5,as_of-timedelta(seconds=config['finalization_seconds']))
        validate(daily,1440,as_of)
    except ValueError as e: return reject('UNAVAILABLE',str(e))
    if len(bars)<20 or len(daily)<20: return reject('WARMUP','INSUFFICIENT_HISTORY')
    b=bars[-1]; close_time=b.t+timedelta(minutes=5)
    structure=aggregate15(bars)
    if len(structure)<3:return reject('WARMUP','INSUFFICIENT_15M_STRUCTURE')
    d['structure_15m_close']=(structure[-1].t+timedelta(minutes=15)).isoformat()
    d['structure_15m_pivots']=pivots(structure,config['pivot_left'],config['pivot_right'])[-4:]
    d.update(last_bar_close=close_time.isoformat(),data_delay_sec=(as_of-close_time).total_seconds(),daily_bias=bias(daily,config))
    local=close_time.astimezone(IST)
    if local.date()!=as_of.astimezone(IST).date() or d['data_delay_sec']>config['max_feed_age_seconds']: return reject('STALE_FEED','STALE_5M')
    if not config['entry_window'][0]<=local.strftime('%H:%M')<=config['entry_window'][1]: return reject('NO_SETUP','OUTSIDE_EXPERIMENT_WINDOW')
    if d['daily_bias']=='NEUTRAL': return reject('NO_SETUP','NEUTRAL_DAILY_BIAS')
    current=[x for x in bars if x.t.astimezone(IST).date()==local.date()]
    if current[0].t.astimezone(IST).strftime('%H:%M')!='09:15':return reject('UNAVAILABLE','MISSING_SESSION_OPEN')
    side='BUY' if d['daily_bias']=='BULLISH' else 'SELL'; sign=1 if side=='BUY' else -1
    # Search causally recent raid, then reclaim, then a strictly later confirmation.
    for i in range(max(14,len(bars)-config['max_reclaim_bars']-config['max_confirmation_bars']-2),len(bars)-1):
        raid=bars[i]
        if raid.t.astimezone(IST).date()!=local.date(): continue
        refs=levels(bars[:i],daily,config)
        for ref in refs:
            if ref['side']!=('LOW' if side=='BUY' else 'HIGH'): continue
            extreme=raid.l if side=='BUY' else raid.h
            if sign*(ref['price']-extreme)<config['sweep_buffer_ticks']*config['tick_size']: continue
            d.update(status='SWEEP_CANDIDATE',liquidity_ref=ref['kind'],liquidity_price=ref['price'])
            reclaim=next((j for j in range(i,min(i+config['max_reclaim_bars']+1,len(bars))) if sign*(bars[j].c-ref['price'])>0),None)
            if reclaim is None: continue
            if len(bars)-1-reclaim>config['max_confirmation_bars']:
                d.update(status='EXPIRED',reason_codes=['CONFIRMATION_TIMEOUT']);continue
            if reclaim>=len(bars)-1:
                d.update(status='WAIT_CONFIRM',reason_codes=['RECLAIM_WITHOUT_LATER_CONFIRM']);continue
            # Earlier confirmed breaks consume this setup; do not emit again on later bars.
            ps=pivots(bars[:reclaim+1],config['pivot_left'],config['pivot_right'])
            thresholds=[p['price'] for p in ps if p['kind']==('HIGH' if side=='BUY' else 'LOW')]
            def confirmation(k):
                gap=fvg(bars[:k+1],config['min_gap_ticks']*config['tick_size'])
                if 'MSS' in config['confirmation'] and thresholds and sign*(bars[k].c-thresholds[-1])>0 and sign*(bars[k-1].c-thresholds[-1])<=0: return 'MSS'
                if 'FVG' in config['confirmation'] and k-2>reclaim and gap and gap['side']==side:return 'FVG'
                if config['turtle_soup_enabled'] and k==reclaim+1 and sign*(bars[k].c-ref['price'])>0:return 'TURTLE_SOUP'
                return None
            first=next((k for k in range(reclaim+1,len(bars)) if confirmation(k)),None)
            if first!=len(bars)-1: continue
            atr=sum(max(x.h-x.l,abs(x.h-bars[k-1].c),abs(x.l-bars[k-1].c)) for k,x in enumerate(bars[-14:],start=len(bars)-14))/14
            if abs(b.c-ref['price'])>atr*config['max_chase_atr']: return reject('NO_SETUP','CHASE_LIMIT')
            observed=min(x.l for x in bars[i:]) if sign==1 else max(x.h for x in bars[i:])
            values,reason=risk(side,b.c,observed,levels(bars[:-1],daily,config),atr,config)
            if not values: return reject('NO_SETUP',reason)
            evidence=dict(bars=[asdict(x) for x in bars],daily=[asdict(x) for x in daily],config=config,raid_index=i,reclaim_index=reclaim,confirmation_index=first)
            key=[config['strategy_version'],symbol,str(local.date()),ref['kind'],raid.t.isoformat(),b.t.isoformat(),side]
            d.update(values,id=digest(key),decision=side,status='SIGNAL',reason_codes=['SWEEP_RECLAIM',confirmation(first),'PROPOSED_NSE'],exchange='NSE',session_date_ist=str(local.date()),market_state='OPEN',data_provider='Yahoo/yfinance best effort',timeframe='5m',sweep_extreme=observed,sweep_bar_close_utc=(raid.t+timedelta(minutes=5)).astimezone(ZoneInfo('UTC')).isoformat(),confirmation_type=confirmation(first),confirmation_bar_ids=[b.t.isoformat()],signal_time_utc=as_of.astimezone(ZoneInfo('UTC')).isoformat(),signal_time_ist=as_of.astimezone(IST).isoformat(),bar_close_time=close_time.isoformat(),earliest_actionable_time=as_of.isoformat(),quality_flags=['DELAYED_RESEARCH','TICK_METADATA_UNVERIFIED'],chart_link='https://www.tradingview.com/chart/mWisj3X4/?symbol=NSE%3A'+symbol.replace('&','%26').replace('-','_')+'&interval=5',evidence=evidence,evidence_ref=digest(evidence),config_sha256=digest(config))
            return d
    if d['status']=='WARMUP': return reject('NO_SETUP','NO_CONFIRMED_SWEEP')
    return d
