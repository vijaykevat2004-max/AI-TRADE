"""Independent, proposed opening-range trend model for shadow research only."""
from datetime import timedelta
from .kernel import IST, digest, validate


def evaluate_trend(symbol, as_of, frames, cfg):
    result = dict(symbol=symbol, status='NO_SETUP', decision='NO_TRADE',
                  reason_codes=[], is_paper=True, execution_enabled=False)
    def reject(status, reason):
        return dict(result, status=status, reason_codes=[reason])
    bars = frames['5m']
    try:
        validate(bars, 5, as_of-timedelta(seconds=cfg['finalization_seconds']))
    except ValueError as exc:
        return reject('UNAVAILABLE', str(exc))
    if len(bars)<21:
        return reject('WARMUP', 'TREND_HISTORY_SHORT')
    last, previous = bars[-1], bars[-2]
    close_time = last.t+timedelta(minutes=5)
    if close_time.date()!=as_of.astimezone(IST).date() or (as_of-close_time).total_seconds()>cfg['max_feed_age_seconds']:
        return reject('STALE_FEED', 'STALE_5M')
    if not cfg['entry_window'][0]<=close_time.astimezone(IST).strftime('%H:%M')<=cfg['entry_window'][1]:
        return reject('NO_SETUP', 'OUTSIDE_EXPERIMENT_WINDOW')
    today=[b for b in bars if b.t.astimezone(IST).date()==last.t.astimezone(IST).date()]
    opening=[b for b in today if '09:15'<=b.t.astimezone(IST).strftime('%H:%M')<'09:30']
    if len(opening)!=3 or today[0].t.astimezone(IST).strftime('%H:%M')!='09:15':
        return reject('UNAVAILABLE', 'MISSING_OPENING_RANGE')
    if len(today)<5:
        return reject('NO_SETUP', 'OPENING_RANGE_NOT_ACTIONABLE')
    high=max(b.h for b in opening); low=min(b.l for b in opening)
    side=1 if last.c>high and previous.c<=high else -1 if last.c<low and previous.c>=low else 0
    if not side:
        return reject('NO_SETUP', 'NO_NEW_OR_BREAKOUT')
    ema=bars[0].c
    for b in bars[1:]:
        ema=ema+2/21*(b.c-ema)
    vwap=sum((b.h+b.l+b.c)/3*b.v for b in today)/sum(b.v for b in today)
    relative_volume=last.v/(sum(b.v for b in bars[-21:-1])/20)
    if side*(last.c-ema)<=0 or side*(last.c-vwap)<=0:
        return reject('NO_SETUP', 'TREND_VWAP_DISAGREE')
    if relative_volume<1.2:
        return reject('NO_SETUP', 'BREAKOUT_VOLUME_LOW')
    atr=sum(max(bars[i].h-bars[i].l,abs(bars[i].h-bars[i-1].c),abs(bars[i].l-bars[i-1].c)) for i in range(len(bars)-14,len(bars)))/14
    boundary=high if side==1 else low
    if side*(last.c-boundary)>atr:
        return reject('NO_SETUP', 'BREAKOUT_CHASE_LIMIT')
    stop=(min(b.l for b in today[-3:])-cfg['stop_buffer_ticks']*cfg['tick_size']) if side==1 else (max(b.h for b in today[-3:])+cfg['stop_buffer_ticks']*cfg['tick_size'])
    distance=side*(last.c-stop)
    cost=last.c*cfg['round_trip_cost_bps']/10000+2*cfg['slippage_ticks']*cfg['tick_size']
    if distance<=0 or distance>2*atr:
        return reject('NO_SETUP', 'TREND_STOP_TOO_WIDE')
    target=last.c+side*2*distance
    net_rr=(2*distance-cost)/(distance+cost)
    if net_rr<cfg['min_net_rr']:
        return reject('NO_SETUP', 'NET_RR_TOO_LOW')
    return dict(result, status='SIGNAL', decision='BUY' if side==1 else 'SELL',
                id=digest(['shadow-or-trend-v1',symbol,last.t.isoformat()]),
                strategy_id='shadow_or_trend_v1', version='research-1',
                reason_codes=['OR_BREAKOUT','EMA20_VWAP_ALIGNED','RELATIVE_VOLUME_1_2'],
                entry_reference=last.c, stop=stop, targets=[target],
                estimated_net_rr=net_rr, earliest_actionable_time=as_of.isoformat(),
                bar_close_time=close_time.isoformat(), relative_volume=relative_volume,
                target_basis='PROPOSED_2R_NOT_FORECAST', config_sha256=digest(cfg))
