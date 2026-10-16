import unittest
from datetime import datetime,timedelta
from liquidity.kernel import IST,Bar
from liquidity.runtime import config
from liquidity.feed import reconcile,bounded_context

class FeedTests(unittest.TestCase):
    def rows(self):
        t=datetime(2026,10,16,9,15,tzinfo=IST)
        return [Bar(t+timedelta(minutes=i),100,102,99,101,0 if i==0 else 10) for i in range(5)]
    def test_observed_volume_sum_and_ohlc(self):
        rows=self.rows();now=rows[0].t+timedelta(minutes=10)
        out,q=reconcile([Bar(rows[0].t,100,102,99,101,0)],rows,now,config())
        self.assertEqual(out[0].v,40);self.assertEqual(q['repaired_count'],1);self.assertFalse(q['synthetic_bars'])
    def test_missing_duplicate_or_unclosed_minute_cannot_fill(self):
        rows=self.rows();now=rows[0].t+timedelta(minutes=10)
        for inputs in (rows[:-1],rows+[rows[-1]]):
            out,q=reconcile([],inputs,now,config());self.assertEqual(out,[])
        self.assertEqual(reconcile([],rows,rows[0].t+timedelta(minutes=5),config())[0],[])
    def test_conflicting_price_or_negative_volume_cannot_repair(self):
        rows=self.rows();now=rows[0].t+timedelta(minutes=10)
        out,q=reconcile([Bar(rows[0].t,105,106,99,101,0)],rows,now,config())
        self.assertEqual(out[0].v,0);self.assertEqual(len(q['conflicting_bars']),1)
        rows[-1]=Bar(rows[-1].t,100,102,99,101,-1)
        self.assertEqual(reconcile([],rows,now,config())[0],[])
    def test_only_prior_faults_reset_context(self):
        rows=self.rows();now=rows[0].t+timedelta(minutes=20)
        prior=Bar(rows[0].t-timedelta(days=1),100,102,99,101,0)
        current=[Bar(rows[0].t,100,102,99,101,0),Bar(rows[0].t+timedelta(minutes=5),100,102,99,101,100)]
        out,q=bounded_context([prior]+current,now,config())
        self.assertEqual(out,current);self.assertEqual(q['excluded_prior_bars'],1)
        self.assertEqual(out[0].v,0) # current fault must still fail kernel validation
    def test_effective_action_day_keeps_intraday_but_requires_daily_warmup(self):
        from unittest.mock import patch
        import pandas as pd
        from liquidity.runtime import source
        from liquidity.kernel import evaluate
        now=datetime(2026,10,16,11,30,tzinfo=IST)
        index=pd.date_range('2026-10-16 09:15',periods=20,freq='5min',tz=IST)
        intraday=pd.DataFrame(dict(Open=100,High=102,Low=99,Close=101,Volume=100),index=index)
        daily=pd.DataFrame(dict(Open=[100,100],High=[102,102],Low=[99,99],Close=[101,101],Volume=[100,100],Dividends=[0,12]),index=pd.date_range('2026-10-15',periods=2,tz=IST))
        with patch('yfinance.Ticker') as ticker:
            ticker.return_value.history.side_effect=[intraday,daily]
            frames=source('TEST',now,dict(config(),daily_price_basis='RAW_POST_ACTION'))
        self.assertEqual(len(frames['5m']),20);self.assertEqual(frames['1d'],[])
        self.assertEqual(evaluate('TEST',now,frames,config())['status'],'WARMUP')
    def test_historical_seed_does_not_fill_prior_or_current_gaps(self):
        t=datetime(2026,10,15,10,tzinfo=IST);now=t+timedelta(days=1,hours=2)
        seed=[Bar(t+timedelta(minutes=5*i),100,102,99,101,100) for i in range(25)]
        bad=Bar(seed[-1].t+timedelta(minutes=5),100,102,99,101,0)
        current=[Bar(now.replace(hour=9,minute=15),100,102,99,101,100),Bar(now.replace(hour=9,minute=25),100,102,99,101,100)]
        out,q=bounded_context(seed+[bad]+current,now,config())
        self.assertEqual(out,seed+current);self.assertEqual(q['seed_bars'],25)
        from liquidity.kernel import validate
        with self.assertRaisesRegex(ValueError,'GAP_IN_SESSION'):validate(out,5,now)
    def test_adjusted_daily_and_intraday_share_provider_basis(self):
        import pandas as pd
        from unittest.mock import patch
        from liquidity.runtime import source
        now=datetime(2026,10,16,11,30,tzinfo=IST)
        dates=pd.date_range('2026-09-01',periods=46,tz=IST)
        daily=pd.DataFrame(dict(Open=100,High=102,Low=99,Close=100,Volume=100,Dividends=0,**{'Stock Splits':0,'Adj Close':90}),index=dates)
        daily.loc[dates[-1],'Adj Close']=100;daily.loc[dates[-1],'Dividends']=10
        prior=pd.date_range('2026-10-15 09:15',periods=25,freq='5min',tz=IST)
        today=pd.date_range('2026-10-16 09:15',periods=20,freq='5min',tz=IST)
        intraday=pd.DataFrame(dict(Open=100,High=102,Low=99,Close=100,Volume=100),index=prior.append(today))
        with patch('yfinance.Ticker') as ticker:
            ticker.return_value.history.side_effect=[intraday,daily]
            frames=source('TEST',now,config())
        self.assertEqual(frames['1d'][-1].c,90);self.assertEqual(frames['5m'][0].c,90)
        self.assertEqual(frames['5m'][-1].c,100)
        self.assertEqual(frames['_quality']['daily_price_basis'],'PROVIDER_ADJUSTED')
