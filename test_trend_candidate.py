import unittest
from datetime import datetime, timedelta
from liquidity.kernel import Bar, IST
from liquidity.runtime import config
from liquidity.trend_candidate import evaluate_trend


class TrendCandidateTests(unittest.TestCase):
    def fixture(self):
        start=datetime(2026,10,16,9,15,tzinfo=IST)
        bars=[Bar(start+timedelta(minutes=5*i),100,102 if i<3 else 101,99,100,100) for i in range(22)]
        bars[-1]=Bar(bars[-1].t,100,103.5,100,103,500)
        cfg=config();cfg['entry_window']=['09:30','14:30']
        return bars,cfg,bars[-1].t+timedelta(minutes=6,seconds=30)

    def test_new_confirmed_breakout_has_valid_paper_levels(self):
        bars,cfg,now=self.fixture()
        row=evaluate_trend('TEST',now,{'5m':bars},cfg)
        self.assertEqual(row['decision'],'BUY',row)
        self.assertLess(row['stop'],row['entry_reference'])
        self.assertGreater(row['targets'][0],row['entry_reference'])
        self.assertFalse(row['execution_enabled'])
        self.assertEqual(row['target_basis'],'PROPOSED_2R_NOT_FORECAST')

    def test_unclosed_and_missing_bars_are_blocked(self):
        bars,cfg,now=self.fixture()
        self.assertEqual(evaluate_trend('TEST',now-timedelta(minutes=2),{'5m':bars},cfg)['status'],'UNAVAILABLE')
        self.assertEqual(evaluate_trend('TEST',now,{'5m':bars[1:]},cfg)['status'],'UNAVAILABLE')

    def test_low_volume_is_not_forced_into_a_signal(self):
        bars,cfg,now=self.fixture()
        b=bars[-1];bars[-1]=Bar(b.t,b.o,b.h,b.l,b.c,100)
        self.assertEqual(evaluate_trend('TEST',now,{'5m':bars},cfg)['reason_codes'],['BREAKOUT_VOLUME_LOW'])
