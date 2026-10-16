"""Retrospective all-symbol causal-prefix audit; never creates a live trade."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from pathlib import Path
import json
from liquidity.runtime import source,config
from liquidity.kernel import evaluate,IST,digest
from monitor import universe

def main():
    now=datetime.now(IST);cfg=config();symbols,manifest=universe()
    def inspect(symbol):
        result=dict(symbol=symbol,native_chart_visual='NOT_VERIFIED_BROWSER_CONNECTION_UNAVAILABLE',prefixes=0,reasons={},retrospective_setups=[],risk_failures=[])
        try:
            frames=source(symbol,now,cfg);bars=frames['5m'];result['quality']=frames.get('_quality',{})
            for i,b in enumerate(bars):
                if b.t.date()!=now.date():continue
                as_of=b.t+timedelta(minutes=5,seconds=cfg['finalization_seconds'])
                if as_of>now:continue
                decision=evaluate(symbol,as_of,dict(frames,**{'5m':bars[:i+1]}),cfg)
                result['prefixes']+=1
                reason=(decision.get('reason_codes') or [decision['status']])[0]
                result['reasons'][reason]=result['reasons'].get(reason,0)+1
                if decision['status']=='SIGNAL':
                    s=1 if decision['decision']=='BUY' else -1
                    if not (s*(decision['entry_reference']-decision['stop'])>0 and s*(decision['targets'][0]-decision['entry_reference'])>0 and decision['estimated_net_rr']>=cfg['min_net_rr']):result['risk_failures'].append(decision['id'])
                    result['retrospective_setups'].append({k:decision.get(k) for k in ('id','decision','bar_close_time','entry_reference','stop','targets','estimated_net_rr','chart_link','evidence_ref')})
            result['latest']=evaluate(symbol,now,frames,cfg)['status']
        except Exception as e:result['error']=str(e)[:200]
        return result
    with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(inspect,symbols))
    report=dict(collected_at=now.isoformat(),universe_hash=manifest,config_hash=digest(cfg),version=cfg['strategy_version'],symbols=rows,requested=50,completed=sum('error' not in r for r in rows),prefixes=sum(r['prefixes'] for r in rows),retrospective_setups=sum(len(r['retrospective_setups']) for r in rows),risk_invariant_failures=sum(len(r['risk_failures']) for r in rows),native_charts_verified=0,warning='Retrospective revised-source audit is not evidence a signal was observed live; no alerts, paper entries or orders created')
    Path('reports').mkdir(exist_ok=True);Path('reports/audit50.json').write_text(json.dumps(report,indent=2,default=str))
    print(json.dumps({k:v for k,v in report.items() if k!='symbols'}))

if __name__=='__main__':main()
