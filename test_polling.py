import tempfile,unittest
from pathlib import Path
from datetime import datetime,timedelta
from unittest.mock import patch
from liquidity.runtime import Store,Supervisor,config
from liquidity.kernel import Bar,IST
from liquidity.paper import records

class PollingTests(unittest.TestCase):
    def test_intermediate_confirmation_reaches_paper_and_outbox_once(self):
        now=datetime(2026,10,16,11,22,tzinfo=IST)
        start=now.replace(hour=9,minute=15)
        bars=[Bar(start+timedelta(minutes=5*i),100,102,99,101,100) for i in range(25)]
        days=[Bar(start.replace(hour=0)-timedelta(days=i),100,102,99,101,100) for i in range(25,0,-1)]
        def kernel(symbol,at,frames,cfg):
            common=dict(symbol=symbol,strategy_id=cfg['strategy_id'],last_bar_close=(frames['5m'][-1].t+timedelta(minutes=5)).isoformat(),reason_codes=[])
            if symbol=='S0' and len(frames['5m'])==24:
                return dict(common,id='a'*64,status='SIGNAL',decision='BUY',earliest_actionable_time=at.isoformat(),session_date_ist=str(at.date()),entry_reference=100,stop=98,targets=[104])
            return dict(common,status='NO_SETUP',decision='NO_TRADE')
        with tempfile.TemporaryDirectory(dir='.') as tmp:
            store=Store(Path(tmp)/'s.sqlite')
            runner=Supervisor(['S'+str(i) for i in range(50)],store,{'verified':True,'year':2026},provider=lambda *args:{'5m':bars,'1d':days})
            with patch('liquidity.runtime.evaluate',side_effect=kernel):
                first=runner.tick(now);second=runner.tick(now+timedelta(minutes=5))
            self.assertEqual(len(first['signals']),1);self.assertEqual(len(second['signals']),0)
            self.assertEqual(len(records(store)),1);self.assertEqual(len(store.pending()),1)
            self.assertEqual(records(store)[0]['signal']['earliest_actionable_time'],now.isoformat())
            self.assertEqual(store.states()['S0']['status'],'NO_SETUP')
