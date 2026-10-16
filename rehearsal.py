"""Existing infrastructure rehearsal. Never places trades or enables production."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from liquidity.kernel import IST
from liquidity.runtime import Store, Supervisor, load_calendar,config,dispatch,GitHubNotifications
from monitor import universe,GitHub,UNIVERSE_EVIDENCE

def serve(store,port):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            states=list(store.states().values())
            if self.path=='/health':body={'process':'alive','agents':len(states),'execution_enabled':False};code=200
            elif self.path=='/ready':body={'ready':False,'reason':'REHEARSAL_ONLY; production acceptance incomplete'};code=503
            elif self.path=='/agents/status':body=states;code=200
            elif self.path=='/signals':body=[x for x in states if x.get('decision') in ('BUY','SELL')];code=200
            else:body={'error':'NOT_FOUND'};code=404
            self.send_response(code);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(body,default=str).encode())
        def log_message(self,*args):pass
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()

def main():
    p=argparse.ArgumentParser();p.add_argument('--serve',action='store_true');p.add_argument('--publish-health',action='store_true');p.add_argument('--paper-followup',action='store_true');p.add_argument('--db',default='state.sqlite');p.add_argument('--port',type=int,default=8765);a=p.parse_args()
    Path('reports').mkdir(exist_ok=True)
    now=datetime.now(IST)
    try:symbols,manifest_hash=universe()
    except RuntimeError:
        failure=dict(collected_at=now.isoformat(),strategy_id=config()['strategy_id'],status='UNIVERSE_UNAVAILABLE',requested=50,evaluated=0,agents=[],signals=[],symbols=[],production_ready=False,execution_authority=False,universe=UNIVERSE_EVIDENCE)
        Path('reports/liquidity-latest.json').write_text(json.dumps(failure,indent=2))
        if a.publish_health:
            gh=GitHub();gh.health(failure,gh.issues())
        raise
    store=Store(a.db)
    Path('reports/universe.json').write_text(json.dumps(dict(symbols=symbols,sha256=manifest_hash,fetched_at=now.isoformat()),indent=2))
    supervisor=Supervisor(symbols,store,load_calendar(now),prepare_closed=True)
    from liquidity.paper import restore_journal,sync_journal
    gh=GitHub() if a.publish_health else None
    issues=gh.issues() if gh else []
    if gh:restore_journal(store,issues)
    if a.serve:threading.Thread(target=serve,args=(store,a.port),daemon=True).start()
    while True:
        now=datetime.now(IST);supervisor.calendar=load_calendar(now)
        report=supervisor.tick(now)
        report['universe']=dict(UNIVERSE_EVIDENCE)
        report['coverage']=dict(requested=50,current_feed_observed=sum(a.get('current_feed',{}).get('status')=='OBSERVED' for a in report['agents']),strategy_history_ready=sum(a['status'] not in ('UNAVAILABLE','STALE_FEED','WARMUP','CALENDAR_UNKNOWN','MARKET_CLOSED') for a in report['agents']),warmup=sum(a['status']=='WARMUP' for a in report['agents']),meaning='Observed feed is a validated recent closed bar; strategy history additionally requires complete context. Neither implies real-time or certified production.')
        report['coverage'].update(history_prepared=sum(a.get('history_preparation',{}).get('status')=='PREPARED' for a in report['agents']),history_pending=sum(a.get('history_preparation',{}).get('status')=='DATA_PENDING' for a in report['agents']))
        if a.paper_followup:
            from liquidity.paper import records,update_symbol,summary
            from liquidity.runtime import source
            errors={}
            for symbol in sorted({r['symbol'] for r in records(store) if r['status'] not in ('CLOSED','AMBIGUOUS','MISSED_SETUP')}):
                try:update_symbol(store,symbol,source(symbol,now,config())['5m'],now,config())
                except Exception as e:errors[symbol]=str(e)[:200]
            report.update(paper_summary=summary(store),paper_followup_errors=errors)
        Path('reports/liquidity-latest.json').write_text(json.dumps(report,indent=2,default=str))
        if a.publish_health:
            issues=gh.issues()
            sync_journal(store,gh,issues)
            # Rehearsal health only; NO new signal notification before acceptance.
            light=dict(report,agents=[{k:v for k,v in x.items() if k!='evidence'} for x in report['agents']])
            gh.health(light,issues)
            if config()['notifications_enabled'] and config()['production_enabled']:
                dispatch(store,GitHubNotifications(gh),datetime.now(IST),supervisor.calendar,enabled=True)
        print(json.dumps({k:v for k,v in report.items() if k not in ('agents','signals','symbols')}),flush=True)
        if not a.serve:break
        time.sleep(60)

if __name__=='__main__':main()
