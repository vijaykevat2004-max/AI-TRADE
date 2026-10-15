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
from monitor import universe,GitHub

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
    p=argparse.ArgumentParser();p.add_argument('--serve',action='store_true');p.add_argument('--publish-health',action='store_true');p.add_argument('--db',default='state.sqlite');p.add_argument('--port',type=int,default=8765);a=p.parse_args()
    symbols,manifest_hash=universe();store=Store(a.db);now=datetime.now(IST)
    Path('reports').mkdir(exist_ok=True)
    Path('reports/universe.json').write_text(json.dumps(dict(symbols=symbols,sha256=manifest_hash,fetched_at=now.isoformat()),indent=2))
    supervisor=Supervisor(symbols,store,load_calendar(now))
    if a.serve:threading.Thread(target=serve,args=(store,a.port),daemon=True).start()
    while True:
        now=datetime.now(IST);supervisor.calendar=load_calendar(now)
        report=supervisor.tick(now)
        Path('reports/liquidity-latest.json').write_text(json.dumps(report,indent=2,default=str))
        if a.publish_health:
            gh=GitHub();issues=gh.issues()
            # Rehearsal health only; NO new signal notification before acceptance.
            light=dict(report,agents=[{k:v for k,v in x.items() if k!='evidence'} for x in report['agents']])
            gh.health(light,issues)
            if config()['notifications_enabled'] and config()['production_enabled']:
                dispatch(store,GitHubNotifications(gh),datetime.now(IST),supervisor.calendar,enabled=True)
        print(json.dumps({k:v for k,v in report.items() if k not in ('agents','signals','symbols')}),flush=True)
        if not a.serve:break
        time.sleep(60)

if __name__=='__main__':main()
