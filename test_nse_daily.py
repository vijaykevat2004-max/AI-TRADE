import unittest
from unittest.mock import patch
from datetime import datetime
from liquidity.kernel import IST,Bar
from liquidity.runtime import config
from liquidity.nse_daily import recover,official_day,_cache

class OfficialDailyTests(unittest.TestCase):
    def fixture(self):
        import pandas as pd
        now=datetime(2026,10,16,12,tzinfo=IST)
        f=pd.DataFrame(dict(Open=100,High=102,Low=99,Close=100,Volume=100,**{'Adj Close':100,'Dividends':0,'Stock Splits':0}),index=pd.to_datetime(['2026-10-14','2026-10-16']).tz_localize(IST))
        intra=pd.DataFrame(index=pd.to_datetime(['2026-10-15 09:15']).tz_localize(IST))
        bar=Bar(datetime(2026,10,15,tzinfo=IST),100,103,98,102,500)
        return now,f,intra,bar
    def test_exact_official_bar_and_provenance_backfill(self):
        now,f,intra,bar=self.fixture()
        with patch('liquidity.nse_daily.official_day',return_value=(bar,100,{'source':'OFFICIAL'})):
            out,proof=recover(f,intra,'TEST',now,config())
        self.assertEqual(out.loc[bar.t,'Close'],102);self.assertEqual(out.loc[bar.t,'Volume'],500)
        self.assertEqual(proof[0]['adjustment_factor'],1)
    def test_conflicting_adjustment_or_previous_close_stays_blocked(self):
        now,f,intra,bar=self.fixture();f.iloc[0,f.columns.get_loc('Adj Close')]=90
        with self.assertRaisesRegex(ValueError,'BRACKETS_CONFLICT'):recover(f,intra,'TEST',now,config())
        f.iloc[0,f.columns.get_loc('Adj Close')]=100
        with patch('liquidity.nse_daily.official_day',return_value=(bar,99,{})):
            with self.assertRaisesRegex(ValueError,'PREVIOUS_CLOSE_CONFLICT'):recover(f,intra,'TEST',now,config())
    def test_official_wrong_date_and_duplicate_series_rejected(self):
        now,_,_,bar=self.fixture();header='SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE, TTL_TRD_QNTY\n'
        row='TEST, EQ, 14-Oct-2026, 100, 100, 103, 98, 102, 500\n'
        _cache.clear()
        with patch('monitor.request',return_value=header+row):
            with self.assertRaisesRegex(ValueError,'DATE_MISMATCH'):official_day(bar.t.date(),'TEST',now)
        _cache.clear()
        with patch('monitor.request',return_value=header+row+row):
            with self.assertRaisesRegex(ValueError,'NOT_UNIQUE'):official_day(bar.t.date(),'TEST',now)
        _cache.clear()
