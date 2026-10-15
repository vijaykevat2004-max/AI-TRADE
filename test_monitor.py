import unittest
from unittest.mock import patch
from datetime import datetime, timedelta
import tempfile
import os
import types
import monitor as m


def fixture():
    rows = []
    day = datetime(2026, 10, 1, 9, 15, tzinfo=m.IST)
    while len(rows) < 175:
        if day.weekday() < 5:
            for j in range(25):
                c = 100 + len(rows) * .05
                rows.append(dict(t=day+timedelta(minutes=j*15), o=c-.02, h=c+.1, l=c-.1, c=c, v=100))
        day += timedelta(days=1)
    return rows


class MonitorTests(unittest.TestCase):
    def test_5m_recovery_requires_three_real_bars(self):
        import pandas as pd
        start = datetime(2026,10,15,9,15,tzinfo=m.IST)
        frame = pd.DataFrame(dict(Open=[100,101,102], High=[102,103,104], Low=[99,100,101], Close=[101,102,103], Volume=[10,20,30]),index=pd.date_range(start,periods=3,freq='5min'))
        ticker = types.SimpleNamespace(history=lambda **kw:frame)
        result = m.recover_5m(ticker,start+timedelta(minutes=20))
        self.assertEqual(result.iloc[0].Volume,60)
        self.assertEqual(result.iloc[0].Close,103)
        ticker.history = lambda **kw:frame.iloc[:2]
        with self.assertRaises(ValueError):
            m.recover_5m(ticker,start+timedelta(minutes=20))

    def test_publish_dedup_and_holiday(self):
        import pandas as pd
        bars = fixture()
        bars[-1].update(o=110, h=120, l=110, c=119, v=200)
        frame = pd.DataFrame([dict(Open=b['o'], High=b['h'], Low=b['l'], Close=b['c'], Volume=b['v']) for b in bars], index=pd.DatetimeIndex([b['t'] for b in bars]))
        now = bars[-1]['t']+timedelta(minutes=35)
        items = []
        class FakeGitHub:
            def issues(self): return list(items)
            def create(self, title, body): items.append(dict(title=title, body=body))
            def health(self, report, issues): pass
        ticker = types.SimpleNamespace(history=lambda **kwargs: frame)
        with tempfile.TemporaryDirectory(dir='.') as d:
            old = os.getcwd()
            try:
                os.chdir(d)
                with patch.object(m, 'universe', return_value=([f'S{i}' for i in range(50)], 'testhash')), patch.object(m, 'holiday_status', return_value=('REGULAR_WEEKDAY','fixture')), patch.object(m, 'GitHub', FakeGitHub), patch.object(m.time, 'sleep'), patch.dict('sys.modules', yfinance=types.SimpleNamespace(Ticker=lambda s:ticker)):
                    first = m.scan(now, True)
                    self.assertEqual(first['evaluated'], 50)
                    self.assertEqual(len(items), 50)
                    second = m.scan(now, True)
                    self.assertEqual(len(items), 50)
                    self.assertEqual(second['status'], 'OK')
                with patch.object(m, 'holiday_status', return_value=('HOLIDAY','fixture')), patch.object(m, 'universe', side_effect=AssertionError('holiday must skip data')):
                    self.assertEqual(m.scan(now)['status'], 'HOLIDAY')
            finally:
                os.chdir(old)

    def test_breakout_risk_and_no_lookahead(self):
        bars = fixture()
        b = dict(bars[150], c=112, h=112.1, l=110, o=110, v=200)
        bars[150] = b
        signal = m.evaluate(bars, 150)
        self.assertEqual(signal['direction'], 'LONG')
        self.assertLess(signal['stop'], signal['reference_close'])
        self.assertAlmostEqual(signal['target_2R']-112, 2*(112-signal['stop']), places=2)
        bars[151]['c'] = 999999
        self.assertEqual(signal, m.evaluate(bars, 150))

    def test_volume_filter_and_warmup(self):
        bars = fixture()
        self.assertIsNone(m.evaluate(bars, 149))
        bars[150].update(c=200, h=201, v=100)
        self.assertIsNone(m.evaluate(bars, 150))

    def test_bearish_signal(self):
        bars = fixture()
        for b in bars:
            b.update(o=300-b['o'], c=300-b['c'], h=300-b['l'], l=300-b['h'])
        bars[150].update(c=180, l=179, h=190, o=190, v=200)
        signal = m.evaluate(bars, 150)
        self.assertEqual(signal['direction'], 'SHORT')
        self.assertGreater(signal['stop'], signal['reference_close'])
        self.assertLess(signal['target_2R'], signal['reference_close'])

    def test_session_boundaries(self):
        self.assertTrue(m.session_bar(datetime(2026, 10, 15, 9, 15, tzinfo=m.IST)))
        self.assertFalse(m.session_bar(datetime(2026, 10, 15, 15, 30, tzinfo=m.IST)))
        self.assertFalse(m.session_bar(datetime(2026, 10, 17, 9, 15, tzinfo=m.IST)))
        self.assertEqual(m.expected_close(datetime(2026, 10, 15, 16, 10, tzinfo=m.IST)).hour, 15)

    def test_universe_fail_closed(self):
        with patch.object(m, 'request', return_value='Symbol,Series\nRELIANCE,EQ\n'):
            with self.assertRaises(ValueError):
                m.universe()
        raw = 'Symbol,Series\n' + '\n'.join(f'S{i},EQ' for i in range(50))
        with patch.object(m, 'request', return_value=raw):
            self.assertEqual(len(m.universe()[0]), 50)
        with patch.object(m, 'request', return_value=raw.replace('S49', 'S48')):
            with self.assertRaises(ValueError):
                m.universe()

    def test_weekend_does_not_fetch(self):
        with tempfile.TemporaryDirectory(dir='.') as d:
            old = os.getcwd()
            try:
                os.chdir(d)
                with patch.object(m, 'universe', side_effect=AssertionError('must not fetch')):
                    self.assertEqual(m.scan(datetime(2026, 10, 17, 11, tzinfo=m.IST))['status'], 'OUTSIDE_POLL_WINDOW')
            finally:
                os.chdir(old)

    def test_closed_bar_grace_and_invalid_data(self):
        import pandas as pd
        t = datetime(2026, 10, 15, 9, 15, tzinfo=m.IST)
        frame = pd.DataFrame(dict(Open=[100, 101], High=[102, 103], Low=[99,100], Close=[101,102], Volume=[100,200]), index=pd.DatetimeIndex([t,t+timedelta(minutes=15)]))
        self.assertEqual(len(m.clean_bars(frame, t+timedelta(minutes=15))), 0)
        self.assertEqual(len(m.clean_bars(frame, t+timedelta(minutes=17))), 1)
        frame.iloc[0, 4] = 0
        with self.assertRaises(ValueError):
            m.clean_bars(frame, t+timedelta(minutes=17))


if __name__ == '__main__':
    unittest.main()
