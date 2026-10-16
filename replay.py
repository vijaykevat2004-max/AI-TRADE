"""Read-only chronological replay. Real source data never becomes a fresh alert."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime,timedelta
import json
from pathlib import Path
import statistics
from liquidity.kernel import IST,evaluate,digest
from liquidity.runtime import config,source
from monitor import universe

def outcome(signal, future, cfg):
    sign=1 if signal['decision']=='BUY' else -1
    entry=signal['entry_reference'];stop=signal['stop'];target=signal['targets'][0]
    exit_price=entry;why='NO_FUTURE_BAR';exit_time=None
    # First subsequent bar only: never fill before confirmation close.
    for b in future:
        if b.t.astimezone(IST).date()!=datetime.fromisoformat(signal['bar_close_time']).astimezone(IST).date():break
        hit_stop=b.l<=stop if sign==1 else b.h>=stop
        hit_target=b.h>=target if sign==1 else b.l<=target
        exit_price=b.c;exit_time=(b.t+timedelta(minutes=5)).isoformat();why='SESSION_TIMEOUT'
        if hit_stop:
            # A gap through stop cannot fill at a more favorable theoretical stop.
            exit_price=min(stop,b.o) if sign==1 else max(stop,b.o);why='STOP_OR_AMBIGUOUS';break
        if hit_target:exit_price=target;why='TARGET';break
        if b.t.astimezone(IST).strftime('%H:%M')>=cfg['expiry']:break
    if exit_time is None:return None
    cost=entry*cfg['round_trip_cost_bps']/10000+2*cfg['slippage_ticks']*cfg['tick_size']
    net=(sign*(exit_price-entry)-cost)/(abs(entry-stop)+cost)
    return dict(id=signal['id'],symbol=signal['symbol'],signal_time=signal['signal_time_ist'],bar_close=signal['bar_close_time'],net_r=net,exit=exit_time,exit_reason=why)

def main():
    now=datetime.now(IST);cfg=config();symbols,universe_hash=universe();Path('reports').mkdir(exist_ok=True)
    report=dict(collected_at=now.isoformat(),mode='HISTORICAL_REPLAY_NOT_LIVE',strategy_id=cfg['strategy_id'],config_hash=digest(cfg),universe_hash=universe_hash,requested=50,usable=0,failures={},decisions={},trades=[],baseline='NOT_COMPARABLE: legacy 150-bar 15m warmup exceeds five-session intraday window',out_of_sample='Last two available sessions per symbol; no tuning or selection on this sample',provider='Yahoo/yfinance unadjusted; best effort',production_ready=False)
    def run(symbol):
        try:
            frames=source(symbol,now,cfg);bars=frames['5m'];days=sorted({b.t.astimezone(IST).date() for b in bars})
            if len(days)<3:raise ValueError('INSUFFICIENT_SESSION_HISTORY')
            oos=set(days[-2:]);decisions={};trades=[];seen=set()
            for i,b in enumerate(bars):
                if b.t.astimezone(IST).date() not in oos:continue
                as_of=b.t+timedelta(minutes=5,seconds=cfg['finalization_seconds'])
                decision=evaluate(symbol,as_of,{'5m':bars[:i+1],'1d':frames['1d']},cfg)
                reason=(decision.get('reason_codes') or [decision['status']])[0]
                decisions[reason]=decisions.get(reason,0)+1
                if decision.get('id') and decision['id'] not in seen:
                    seen.add(decision['id']);trade=outcome(decision,bars[i+1:],cfg)
                    if trade:trades.append(trade)
            Path('reports/source-'+symbol.replace('&','_')+'.json').write_text(json.dumps({k:[asdict(b) for b in v] for k,v in frames.items()},default=str))
            invalid={'INVALID_OHLCV','GAP_IN_SESSION','UNCONFIRMED_OR_NAIVE_BAR','DUPLICATE_OR_UNSORTED_BAR','OFF_GRID_BAR','INSUFFICIENT_HISTORY','INSUFFICIENT_15M_STRUCTURE'}
            error='NO_USABLE_OOS_PREFIX: '+','.join(sorted(decisions)) if not decisions or set(decisions).issubset(invalid) else None
            return symbol,decisions,trades,error
        except Exception as e:return symbol,{},[],str(e)[:220]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for symbol,counts,trades,error in pool.map(run,symbols):
            if error:report['failures'][symbol]=error
            else:report['usable']+=1
            report['decisions'][symbol]=counts;report['trades'].extend(trades)
    trades=sorted(report['trades'],key=lambda t:t['signal_time']);values=[t['net_r'] for t in trades]
    equity=peak=drawdown=0
    for x in values:equity+=x;peak=max(peak,equity);drawdown=max(drawdown,peak-equity)
    report['metrics']=dict(trades=len(values),win_rate=sum(x>0 for x in values)/len(values) if values else None,profit_factor=sum(max(0,x) for x in values)/abs(sum(min(0,x) for x in values)) if any(x<0 for x in values) else None,expectancy_r=statistics.mean(values) if values else None,max_drawdown_r=drawdown if values else None,confidence_interval='NOT_ESTIMATED: small/overlapping observations; no calibrated accuracy claim',portfolio_assumptions='Independent paper setups; no position sizing or capital allocation; drawdown is unweighted chronological R sum, not investable portfolio')
    Path('reports/replay.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('decisions','trades')},indent=2))

if __name__=='__main__':main()
