import tempfile,unittest
from pathlib import Path
from datetime import datetime,timedelta
from liquidity.runtime import Store,config,Supervisor
from liquidity.kernel import Bar,IST
from liquidity.history import retain

class HistoryTests(unittest.TestCase):
    def fixture(self):
        now=datetime(2026,10,16,12,tzinfo=IST);start=now.replace(hour=9,minute=15)
        bars=[Bar(start+timedelta(minutes=5*i),100,102,99,101,100) for i in range(25)]
        days=[Bar(start.replace(hour=0)-timedelta(days=i),100,102,99,101,100) for i in range(25,0,-1)]
        return now,dict({'5m':bars,'1d':days})
    def test_restart_restores_observed_missing_bar_without_invention(self):
        now,frames=self.fixture()
        with tempfile.TemporaryDirectory(dir='.') as tmp:
            st=Store(Path(tmp)/'state.sqlite');retain(st,'TEST',frames,now,config())
            partial=dict(frames,**{'5m':frames['5m'][1:]})
            restored=retain(Store(st.path),'TEST',partial,now,config())
            self.assertEqual(restored['5m'],frames['5m'])
            empty=retain(Store(st.path),'NEW',partial,now,config())
            self.assertEqual(len(empty['5m']),24) # no cache means no invented opening bar
    def test_current_bad_candle_is_not_hidden_by_valid_cache(self):
        now,frames=self.fixture()
        with tempfile.TemporaryDirectory(dir='.') as tmp:
            st=Store(Path(tmp)/'s.sqlite');retain(st,'TEST',frames,now,config())
            bad=Bar(frames['5m'][-1].t,100,102,99,101,0)
            out=retain(st,'TEST',dict(frames,**{'5m':[bad]}),now,config())
            self.assertEqual(out['5m'][-1].v,0)
    def test_action_reset_cannot_restore_old_regime_from_cache(self):
        now,frames=self.fixture()
        with tempfile.TemporaryDirectory(dir='.') as tmp:
            st=Store(Path(tmp)/'s.sqlite');retain(st,'TEST',frames,now,config())
            out=retain(st,'TEST',{'5m':frames['5m'],'1d':[],'_quality':{'corporate_action_reset':'2026-10-16'}},now,config())
            self.assertEqual(out['1d'],[])
    def test_closed_session_prepares_without_emitting_trade(self):
        now,frames=self.fixture();now=now.replace(hour=20)
        with tempfile.TemporaryDirectory(dir='.') as tmp:
            st=Store(Path(tmp)/'s.sqlite')
            report=Supervisor(['S'+str(i) for i in range(50)],st,{'verified':True,'year':2026},provider=lambda *args:frames,prepare_closed=True).tick(now)
            self.assertEqual(report['signals'],[])
            self.assertTrue(all(a['status']=='MARKET_CLOSED' and a['history_preparation']['status']=='PREPARED' for a in report['agents']))
    def test_adjustment_revision_drops_cached_price_basis(self):
        now,frames=self.fixture()
        with tempfile.TemporaryDirectory(dir='.') as tmp:
            st=Store(Path(tmp)/'s.sqlite')
            frames['_quality']={'daily_price_basis':'PROVIDER_ADJUSTED','adjustment_factors':{'2026-10-16':1}}
            retain(st,'TEST',frames,now,config())
            new={'5m':[],'1d':[],'_quality':{'daily_price_basis':'PROVIDER_ADJUSTED','adjustment_factors':{'2026-10-16':0.9}}}
            out=retain(st,'TEST',new,now,config())
            self.assertEqual(out['5m'],[]);self.assertEqual(out['1d'],[])
    def test_fifty_adjusted_workers_persist_without_lock_upgrade_failure(self):
        now,frames=self.fixture();frames['_quality']={'daily_price_basis':'PROVIDER_ADJUSTED','adjustment_factors':{'2026-10-16':1}}
        with tempfile.TemporaryDirectory(dir='.') as tmp:
            st=Store(Path(tmp)/'s.sqlite')
            report=Supervisor(['S'+str(i) for i in range(50)],st,{'verified':True,'year':2026},provider=lambda *args:frames).tick(now)
            self.assertFalse(any(a['status']=='UNAVAILABLE' for a in report['agents']))
            with st.connect() as db:self.assertEqual(db.execute('SELECT COUNT(DISTINCT symbol) FROM history').fetchone()[0],50)
