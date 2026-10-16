"""Bounded supervisor, SQLite durable state/outbox and keyless rehearsal adapter."""
import concurrent.futures
from contextlib import contextmanager
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
import time
from .kernel import Bar, IST, evaluate, digest,validate

ROOT=Path(__file__).resolve().parents[1]

def config(): return json.loads((ROOT/'config/strategy.json').read_text())

def session(now, calendar):
    t=now.astimezone(IST); date=str(t.date()); clock=t.strftime('%H:%M')
    if date in calendar.get('special_sessions',{}):
        opening,closing=calendar['special_sessions'][date]
        return 'OPEN' if opening<=clock<closing else 'MARKET_CLOSED'
    if t.weekday()>=5 or date in calendar.get('holidays',[]):return 'MARKET_CLOSED'
    if not '09:15'<=clock<'15:30':return 'MARKET_CLOSED'
    if calendar.get('year')!=t.year or not calendar.get('verified'):return 'CALENDAR_UNKNOWN'
    return 'OPEN'

class Store:
    def __init__(self,path):
        self.path=str(path)
        with self.connect() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS agents(symbol TEXT PRIMARY KEY, state TEXT NOT NULL); CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY, payload TEXT NOT NULL, sent INTEGER DEFAULT 0, attempts INTEGER DEFAULT 0, error TEXT);')
            columns={row[1] for row in db.execute('PRAGMA table_info(outbox)')}
            for name,definition in [('next_try','TEXT'),('status',"TEXT DEFAULT 'PENDING'")]:
                if name not in columns:db.execute('ALTER TABLE outbox ADD COLUMN '+name+' '+definition)
            db.execute('CREATE TABLE IF NOT EXISTS deliveries(id INTEGER PRIMARY KEY, event_id TEXT, at TEXT, outcome TEXT, detail TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS paper(id TEXT PRIMARY KEY,symbol TEXT NOT NULL,record TEXT NOT NULL)')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=20)
        try:
            with db:yield db
        finally:db.close()
    def states(self):
        with self.connect() as db:return {s:json.loads(v) for s,v in db.execute('SELECT symbol,state FROM agents')}
    def save(self,state):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO agents VALUES(?,?)',(state['symbol'],json.dumps(state,default=str)))
            if state.get('decision') in ('BUY','SELL'):
                db.execute('INSERT OR IGNORE INTO outbox(id,payload) VALUES(?,?)',(state['id'],json.dumps(state,default=str)))
    def pending(self):
        with self.connect() as db:return [(i,json.loads(p)) for i,p in db.execute("SELECT id,payload FROM outbox WHERE sent=0 AND status='PENDING' ORDER BY rowid")]
    def delivery(self,id,error=None):
        with self.connect() as db:db.execute('UPDATE outbox SET attempts=attempts+1,error=?,sent=? WHERE id=?',(error,0 if error else 1,id))

def dispatch(store, transport, now, calendar, enabled=False):
    """Transport must implement existing(id) and send(record). Disabled by default.

    Remote ledger reconciles the send-success/local-ack crash window. Repeated
    failures keep durable retry timestamps, with a bounded five-attempt budget.
    """
    if not enabled or session(now,calendar)!='OPEN':return []
    outcomes=[]
    for id,record in store.pending()[:50]:
        with store.connect() as db:
            attempts,next_try=db.execute('SELECT attempts,next_try FROM outbox WHERE id=?',(id,)).fetchone()
        if next_try and datetime.fromisoformat(next_try)>now:continue
        stamp=record.get('signal_time_ist') or record.get('signal_time_utc')
        if not stamp or now-datetime.fromisoformat(stamp)>timedelta(minutes=15) or record.get('session_date_ist')!=str(now.astimezone(IST).date()):
            state='EXPIRED';error='EXPIRED_OR_UNDATED'
        else:
            try:
                if not transport.existing(id):transport.send(record)
                state='SENT';error=None
            except Exception as e:
                state='FAILED' if attempts>=4 else 'PENDING';error=str(e)[:200]
        with store.connect() as db:
            db.execute('UPDATE outbox SET attempts=attempts+1,status=?,sent=?,error=?,next_try=? WHERE id=?',(state,int(state=='SENT'),error,(now+timedelta(seconds=min(900,30*2**attempts))).isoformat(),id))
            db.execute('INSERT INTO deliveries(event_id,at,outcome,detail) VALUES(?,?,?,?)',(id,now.isoformat(),state,error))
        outcomes.append(dict(id=id,status=state))
    return outcomes

class GitHubNotifications:
    def __init__(self,github):self.github=github;self.ledger={i['title'] for i in github.issues()}
    def existing(self,id):return '[NIFTY signal] '+id in self.ledger
    def send(self,record):
        title='[NIFTY signal] '+record['id']
        # Avoid publishing raw market-data snapshots until redistribution rights are verified.
        safe={k:v for k,v in record.items() if k!='evidence'}
        self.github.create(title,'DELAYED PAPER RESEARCH. No orders.\n\n```json\n'+json.dumps(safe,indent=2,default=str)+'\n```')
        self.ledger.add(title)

def source(symbol,now,cfg):
    import yfinance as yf
    ticker=yf.Ticker(symbol+'.NS')
    frames={'5m':ticker.history(period='5d',interval='5m',auto_adjust=False,actions=True,raise_errors=True,timeout=20),'1d':ticker.history(period='6mo',interval='1d',auto_adjust=False,actions=True,raise_errors=True,timeout=20)}
    # Use a documented bounded window, not unrelated six-month action history.
    # Reset BOTH streams after the most recent action. Never invent adjusted bars.
    daily=frames['1d'].sort_index().tail(cfg['daily_lookback'])
    action_dates=[stamp.date() for stamp,row in daily.iterrows() if any(col in daily and float(row[col] or 0)!=0 for col in ('Stock Splits','Dividends'))]
    reset=max(action_dates) if action_dates else None
    if reset:
        # Intraday opening on the effective date is already in the new regime.
        # Daily context still requires fully post-action completed sessions.
        frames={tf:f[[stamp.date()>=reset if tf=='5m' else stamp.date()>reset for stamp in f.index]] for tf,f in frames.items()}
    intraday=frames['5m'].sort_index()
    used_dates=sorted({stamp.date() for stamp in intraday.index})[-3:]
    frames['5m']=intraday[[stamp.date() in used_dates for stamp in intraday.index]]
    result={}
    for tf,f in frames.items():
        if tf=='1d' and f.empty and reset:
            result[tf]=[];continue # explicit daily warmup, not a missing price feed
        if f.empty or f.index.tz is None or f.index.has_duplicates:raise ValueError('EMPTY_OR_INVALID_INDEX_'+tf)
        out=[]
        for stamp,row in f.sort_index().iterrows():
            t=stamp.to_pydatetime().astimezone(IST)
            if tf=='1d' and t.date()>=now.astimezone(IST).date():continue
            if tf=='5m' and t+timedelta(minutes=5,seconds=cfg['finalization_seconds'])>now:continue
            out.append(Bar(t,*[float(row[k]) for k in ('Open','High','Low','Close','Volume')]))
        result[tf]=out[-cfg['daily_lookback']:] if tf=='1d' else out
    try:validate(result['5m'],5,now-timedelta(seconds=cfg['finalization_seconds']))
    except ValueError:
        from .feed import reconcile
        minute=ticker.history(period='5d',interval='1m',auto_adjust=False,actions=True,raise_errors=True,timeout=20)
        if minute.empty or minute.index.tz is None or minute.index.has_duplicates:raise ValueError('INVALID_1M_RECONCILIATION_SOURCE')
        rows=[Bar(stamp.to_pydatetime().astimezone(IST),*[float(row[k]) for k in ('Open','High','Low','Close','Volume')]) for stamp,row in minute.sort_index().iterrows() if stamp.date() in used_dates and (not reset or stamp.date()>=reset)]
        result['5m'],result['_quality']=reconcile(result['5m'],rows,now,cfg)
    from .feed import bounded_context
    result['5m'],context=bounded_context(result['5m'],now,cfg)
    result['_quality']=dict(result.get('_quality',{}),**context)
    if reset:result['_quality']['corporate_action_reset']=str(reset)
    return result

class Supervisor:
    def __init__(self,symbols,store,calendar,provider=source):
        if len(symbols)!=50 or len(set(symbols))!=50:raise ValueError('REQUIRE_EXACTLY_50_SYMBOLS')
        self.symbols=symbols;self.store=store;self.calendar=calendar;self.provider=provider
    def tick(self,now):
        cfg=config(); previous=self.store.states(); market=session(now,self.calendar)
        def agent(symbol):
            old=previous.get(symbol,{})
            base=dict(symbol=symbol,heartbeat=now.isoformat(),market_state=market,strategy_id=cfg['strategy_id'],decision='NO_TRADE',status=market,last_bar_close=old.get('last_bar_close'),watermark=old.get('watermark'),failures=old.get('failures',0))
            if market!='OPEN':return base
            if old.get('retry_at') and datetime.fromisoformat(old['retry_at'])>now:
                return dict(base,status='UNAVAILABLE',reason_codes=['BACKOFF'],retry_at=old['retry_at'])
            try:
                bars=self.provider(symbol,now,cfg)
                decision=evaluate(symbol,now,bars,cfg)
                if '_quality' in bars:decision['feed_reconciliation']=bars['_quality']
                latest=bars['5m'][-1] if bars['5m'] else None
                if latest:
                    age=(now-(latest.t+timedelta(minutes=5))).total_seconds()
                    try:
                        validate([latest],5,now-timedelta(seconds=cfg['finalization_seconds']))
                        decision['current_feed']=dict(status='OBSERVED' if latest.t.date()==now.date() and age<=cfg['max_feed_age_seconds'] else 'STALE',last_close=(latest.t+timedelta(minutes=5)).isoformat(),age_seconds=age,provider='Yahoo/yfinance best effort')
                    except ValueError:decision['current_feed']=dict(status='INVALID')
                # Same prefix may be evaluated again, but a signal already persisted is not resent.
                base.update(decision,watermark=decision.get('last_bar_close'),failures=0)
                from .paper import register,update_symbol
                if decision.get('status')=='SIGNAL':register(self.store,decision)
                update_symbol(self.store,symbol,bars['5m'],now,cfg)
            except Exception as e:
                count=base['failures']+1
                base.update(status='UNAVAILABLE',decision='NO_TRADE',failures=count,reason_codes=[str(e)[:160]],retry_at=(now+timedelta(seconds=min(900,30*2**min(count,5)))).isoformat())
            return base
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(agent,symbol) for symbol in self.symbols]
            for future in concurrent.futures.as_completed(futures):self.store.save(future.result())
        states=self.store.states()
        from .paper import summary,records
        counts={s:sum(x['status']==s for x in states.values()) for s in sorted({x['status'] for x in states.values()})}
        return dict(collected_at=now.isoformat(),strategy_id=cfg['strategy_id'],version=cfg['strategy_version'],status=market if market!='OPEN' else 'REHEARSAL',requested=50,evaluated=sum(x.get('watermark') is not None for x in states.values()),production_ready=False,source='Yahoo/yfinance best effort; latency measured per symbol, not realtime',execution_authority=False,counts=counts,agents=list(states.values()),signals=[x for x in states.values() if x.get('decision') in ('BUY','SELL')],symbols=self.symbols,paper_summary=summary(self.store),paper_trades=records(self.store)[-25:])

def load_calendar(now):
    # Same official endpoint as existing project; unknown must fail closed.
    from monitor import request,HOLIDAYS_URL
    try:
        rows=json.loads(request(HOLIDAYS_URL))['CM']
        dates=[datetime.strptime(r['tradingDate'],'%d-%b-%Y').date() for r in rows]
        if not any(d.year==now.year for d in dates):raise ValueError('YEAR_MISSING')
        return dict(year=now.year,verified=True,holidays=[str(d) for d in dates],special_sessions={},source=HOLIDAYS_URL,special_session_notice_audit='NOT_VERIFIED; production blocked')
    except Exception:return dict(year=now.year,verified=False,holidays=[],special_sessions={})
