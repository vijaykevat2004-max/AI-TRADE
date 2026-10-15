"""Synthetic fixtures are NOT live evidence or a measured trading edge."""
import copy
from datetime import datetime,timedelta
import tempfile
import unittest
from pathlib import Path
from liquidity.kernel import Bar,IST,pivots,fvg,validate,aggregate15,risk,evaluate,levels
from liquidity.runtime import Store,Supervisor,session,config,dispatch

def bar(i=0,o=100,h=102,l=99,c=101,v=100):
    return Bar(datetime(2026,10,15,9,15,tzinfo=IST)+timedelta(minutes=5*i),o,h,l,c,v)

class Tests(unittest.TestCase):
    def synthetic(self):
        cfg=config();cfg['min_net_rr']=0;cfg['max_chase_atr']=3
        daily=[Bar(datetime(2026,9,1,tzinfo=IST)+timedelta(days=i),100,103 if i==10 else 102,92 if i==12 else 95,100,100) for i in range(24)]
        daily[-1]=Bar(daily[-1].t,100,120,99,106,100)
        bars=[bar(i) for i in range(20)]
        bars[13]=bar(13,h=103)
        bars[17]=bar(17,l=98,c=100)
        bars[19]=bar(19,o=101,h=105,l=100,c=104)
        now=bars[-1].t+timedelta(minutes=6,seconds=30)
        return cfg,dict(daily=daily,bars=bars,now=now)
    def test_sweep_later_confirmation_and_replay_identity(self):
        cfg,f=self.synthetic()
        result=evaluate('TEST',f['now'],{'5m':f['bars'],'1d':f['daily']},cfg)
        self.assertEqual(result['decision'],'BUY',result)
        self.assertEqual(result['confirmation_type'],'MSS')
        self.assertLess(result['stop'],result['entry_reference'])
        self.assertGreater(result['targets'][0],result['entry_reference'])
        self.assertEqual(result['id'],evaluate('TEST',f['now'],{'5m':f['bars'],'1d':f['daily']},cfg)['id'])
        before=evaluate('TEST',f['bars'][18].t+timedelta(minutes=6,seconds=30),{'5m':f['bars'][:19],'1d':f['daily']},cfg)
        self.assertEqual(before['decision'],'NO_TRADE')
    def test_stale_and_no_reclaim(self):
        cfg,f=self.synthetic()
        stale=evaluate('TEST',f['now']+timedelta(hours=1),{'5m':f['bars'],'1d':f['daily']},cfg)
        self.assertEqual(stale['status'],'STALE_FEED')
        f['bars'][17]=bar(17,o=99,h=100,l=98,c=98.5)
        f['bars'][18]=bar(18,o=98.5,h=100,l=98,c=98.5)
        f['bars'][19]=bar(19,o=98.5,h=100,l=98,c=98.5)
        self.assertEqual(evaluate('TEST',f['now'],{'5m':f['bars'],'1d':f['daily']},cfg)['decision'],'NO_TRADE')
    def test_expiry_and_daily_future_excluded(self):
        cfg,f=self.synthetic()
        original=evaluate('TEST',f['now'],{'5m':f['bars'],'1d':f['daily']},cfg)
        future=Bar(datetime(2026,10,16,tzinfo=IST),100,1000,1,999,100)
        self.assertEqual(evaluate('TEST',f['now'],{'5m':f['bars'],'1d':f['daily']+[future]},cfg)['id'],original['id'])
        f['bars'][19]=bar(19)
        f['bars'].extend([bar(i) for i in range(20,24)])
        result=evaluate('TEST',bar(23).t+timedelta(minutes=6,seconds=30),{'5m':f['bars'],'1d':f['daily']},cfg)
        self.assertEqual(result['status'],'EXPIRED')
    def test_equal_high_tolerance(self):
        cfg=config()
        b=[bar(i,h=h) for i,h in enumerate([102,102,104,102,102,102,104.05,102,102])]
        refs=levels(b,[bar(h=120)],cfg)
        self.assertTrue(any(r['kind']=='EQUAL_HIGH' for r in refs))
        self.assertEqual(bar().t.utcoffset(),timedelta(hours=5,minutes=30))
    def test_bull_bear_fvg(self):
        self.assertEqual(fvg([bar(h=100,o=99,c=99,l=98),bar(),bar(l=101,o=102,c=103,h=104)],.1)['zone'],[100,101])
        self.assertEqual(fvg([bar(l=105,o=106,c=106,h=107),bar(),bar()],.1)['side'],'SELL')
        self.assertIsNone(fvg([bar(),bar(),bar(l=102.01,o=103,h=104,c=103)],.1))
    def test_pivot_causal_lag(self):
        b=[bar(i,h=h) for i,h in enumerate([102,103,106,103,102])]
        self.assertEqual(pivots(b[:4]),[])
        self.assertEqual(pivots(b)[0]['index'],2)
    def test_bad_bars(self):
        now=bar(10).t
        for b in ([bar(),bar()], [bar(v=0)], [bar(),bar(2)], [bar(11)]):
            with self.assertRaises(ValueError):validate(b,5,now)
    def test_closed_aggregation(self):
        self.assertEqual(aggregate15([bar(),bar(1)]),[])
        self.assertEqual(len(aggregate15([bar(),bar(1),bar(2)])),1)
    def test_risk_and_nearest_target(self):
        cfg=config();cfg['min_net_rr']=0
        r,_=risk('BUY',100,99,[dict(side='HIGH',price=104),dict(side='HIGH',price=103)],1,cfg)
        self.assertEqual(r['targets'],[103]);self.assertLess(r['stop'],100)
        self.assertEqual(risk('BUY',100,101,[],1,cfg)[1],'NO_OPPOSITE_TARGET')
    def test_calendar(self):
        cal=dict(year=2026,verified=True,holidays=['2026-10-15'],special_sessions={})
        t=datetime(2026,10,15,10,tzinfo=IST)
        self.assertEqual(session(t,cal),'MARKET_CLOSED')
        cal['special_sessions']['2026-10-15']=['09:15','12:00']
        self.assertEqual(session(t,cal),'OPEN')
        self.assertEqual(session(t+timedelta(days=2),cal),'MARKET_CLOSED')
        self.assertEqual(session(t,{}),'CALENDAR_UNKNOWN')
    def test_previous_daily_levels(self):
        self.assertEqual(levels([bar()], [bar(h=110)],config())[0]['price'],110)
    def test_warmup_no_signal(self):
        d=evaluate('TEST',bar(10).t,{'5m':[bar()],'1d':[]},config())
        self.assertEqual(d['decision'],'NO_TRADE')
    def test_fifty_restart_outbox_isolation(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp:
            st=Store(Path(tmp)/'state.sqlite');symbols=['S'+str(i) for i in range(50)]
            def provider(symbol,*args):
                if symbol=='S0':raise ValueError('SOURCE_FAULT')
                return {'5m':[],'1d':[]}
            now=datetime(2026,10,15,10,tzinfo=IST);cal=dict(year=2026,verified=True)
            s=Supervisor(symbols,st,cal,provider)
            for i in range(8):r=s.tick(now+timedelta(minutes=i))
            self.assertEqual(len(r['agents']),50)
            self.assertEqual(st.states()['S0']['status'],'UNAVAILABLE')
            self.assertEqual(st.states()['S1']['status'],'WARMUP')
            state=dict(symbol='S1',id='stable-id',decision='BUY',status='SIGNAL')
            st.save(state);st.save(state)
            again=Store(Path(tmp)/'state.sqlite')
            self.assertEqual(len(again.pending()),1)
            again.delivery('stable-id');self.assertEqual(again.pending(),[])
            closed=Supervisor(symbols,again,cal,provider).tick(now.replace(hour=18))
            self.assertEqual(closed['counts'],{'MARKET_CLOSED':50})
    def test_durable_delivery_retry_dedupe_and_expiry(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp:
            store=Store(Path(tmp)/'queue.sqlite');now=datetime(2026,10,15,10,tzinfo=IST)
            store.save(dict(symbol='TEST',id='one',decision='BUY',session_date_ist='2026-10-15',signal_time_ist=now.isoformat()))
            class Transport:
                sent=set();calls=0
                def existing(self,id):return id in self.sent
                def send(self,record):
                    self.calls+=1
                    if self.calls==1:raise RuntimeError('RETRY_ME')
                    self.sent.add(record['id'])
            transport=Transport();cal=dict(year=2026,verified=True)
            self.assertEqual(dispatch(store,transport,now,cal),[])
            self.assertEqual(dispatch(store,transport,now,cal,True)[0]['status'],'PENDING')
            self.assertEqual(dispatch(store,transport,now,cal,True),[])
            store=Store(Path(tmp)/'queue.sqlite')
            self.assertEqual(dispatch(store,transport,now+timedelta(minutes=1),cal,True)[0]['status'],'SENT')
            self.assertEqual(dispatch(store,transport,now+timedelta(minutes=2),cal,True),[])
            store.save(dict(symbol='TEST',id='expired',decision='BUY',session_date_ist='2026-10-15',signal_time_ist=(now-timedelta(hours=1)).isoformat()))
            self.assertEqual(dispatch(store,transport,now,cal,True)[0]['status'],'EXPIRED')

if __name__=='__main__':unittest.main()
