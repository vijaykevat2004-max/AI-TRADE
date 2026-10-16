"""Bounded causal 15m historical research, separate from the active 5m policy."""
import argparse,json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from pathlib import Path
from liquidity.kernel import Bar,IST,evaluate,digest
from liquidity.runtime import config
from liquidity.paper import evaluate_paper
from liquidity.learning import research
from monitor import universe,GitHub

def run_symbol(symbol,now,cfg):
    import yfinance as yf
    result=dict(symbol=symbol,status='SOURCE_FAILED',evaluated=0,rejections={},trades=[])
    try:
        ticker=yf.Ticker(symbol+'.NS')
        intraday=ticker.history(period='60d',interval='15m',auto_adjust=False,actions=True,raise_errors=True)
        daily=ticker.history(period='1y',interval='1d',auto_adjust=False,actions=True,raise_errors=True)
        def convert(frame):
            if frame.empty or frame.index.tz is None or frame.index.has_duplicates:raise ValueError('INVALID_SOURCE_INDEX')
            return [Bar(t.to_pydatetime(),float(r.Open),float(r.High),float(r.Low),float(r.Close),float(r.Volume)) for t,r in frame.sort_index().iterrows()]
        bars=convert(intraday);days=convert(daily)
        actions=[t.date() for t,r in daily.iterrows() if r.get('Stock Splits',0)!=0 or r.get('Dividends',0)!=0]
        dates=sorted({b.t.astimezone(IST).date() for b in bars});seen=set();usable=set()
        result.update(first_bar=bars[0].t.isoformat(),last_bar=bars[-1].t.isoformat(),available_sessions=len(dates))
        for i,b in enumerate(bars):
            if b.t+timedelta(minutes=15,seconds=cfg['finalization_seconds'])>now:break
            day=b.t.astimezone(IST).date()
            # Corporate-action resets use only actions already effective as of this prefix.
            effective=max((x for x in actions if x<=day),default=None)
            recent=set(dates[max(0,dates.index(day)-2):dates.index(day)+1])
            prefix=[x for x in bars[:i+1] if x.t.astimezone(IST).date() in recent and (effective is None or x.t.date()>effective)]
            history=[x for x in days if x.t.date()<day and (effective is None or x.t.date()>effective)][-60:]
            as_of=b.t+timedelta(minutes=15,seconds=cfg['finalization_seconds'])
            decision=evaluate(symbol,as_of,{'5m':prefix,'1d':history},cfg)
            reason=(decision.get('reason_codes') or [decision['status']])[0]
            result['rejections'][reason]=result['rejections'].get(reason,0)+1
            result['evaluated']+=1
            if decision['status'] in ('NO_SETUP','SIGNAL'):usable.add(str(day))
            if decision['status']=='SIGNAL' and decision['id'] not in seen:
                seen.add(decision['id'])
                safe={k:v for k,v in decision.items() if k not in ('evidence','evidence_canonical','structure_15m_pivots')}
                record=dict(id=decision['id'],symbol=symbol,signal=safe,status='ENTRY_PENDING',result=None,is_paper=True,execution_enabled=False)
                result['trades'].append(evaluate_paper(record,bars[i+1:],now,cfg))
        result.update(status='EVALUATED' if usable else 'NO_VALID_SESSIONS',usable_sessions=len(usable))
    except Exception as e:result['error']=str(e)[:200]
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');p.add_argument('--symbols',nargs='*');a=p.parse_args()
    now=datetime.now(IST);symbols,manifest=universe()
    if a.symbols:
        if any(s not in symbols for s in a.symbols):raise ValueError('OUTSIDE_VALIDATED_UNIVERSE')
        symbols=a.symbols
    cfg=dict(config(),bar_minutes=15,strategy_version='0.1.0-15m-research',max_age_seconds=1200)
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(lambda s:run_symbol(s,now,cfg),symbols))
    trades=[t for r in results for t in r['trades']];closed=[t for t in trades if t['status']=='CLOSED']
    report=dict(collected_at=now.isoformat(),mode='DEGRADED_15M_HISTORICAL_RESEARCH_NOT_ACTIVE_5M',requested=len(symbols),universe_hash=manifest,config_hash=digest(cfg),requested_history='60 calendar days; actual returned range shown per symbol',years_available=False,provider='Yahoo/yfinance best effort, revised history; no point-in-time certification',production_ready=False,execution_enabled=False,symbols=results,summary=dict(setups=len(trades),closed=len(closed),positive=sum(t.get('result')=='POSITIVE' for t in closed),negative=sum(t.get('result')=='NEGATIVE' for t in closed),positive_rate=sum(t.get('result')=='POSITIVE' for t in closed)/len(closed) if closed else None,expectancy_net_r=sum(t['net_r'] for t in closed)/len(closed) if closed else None),learning=research(trades))
    Path('reports').mkdir(exist_ok=True);Path('reports/research.json').write_text(json.dumps(report,indent=2,default=str))
    if a.publish:
        gh=GitHub();issues=gh.issues();title='[NIFTY research] Historical backtest and shadow learning'
        public=dict(report,symbols=[{k:v for k,v in r.items() if k!='trades'} for r in results])
        body='Historical research only; no live orders or automatic policy promotion.\n\n```json\n'+json.dumps(public,indent=2,default=str)+'\n```'
        old=next((i for i in issues if i['title']==title),None)
        gh.api('/issues/'+str(old['number']),dict(body=body),'PATCH') if old else gh.api('/issues',dict(title=title,body=body))
    print(json.dumps(dict(summary=report['summary'],learning=report['learning'],requested=len(symbols),usable_symbols=sum(r['status']=='EVALUATED' for r in results))))

if __name__=='__main__':main()
