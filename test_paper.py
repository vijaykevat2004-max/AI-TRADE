from datetime import datetime,timedelta
from pathlib import Path
import tempfile,unittest
from liquidity.kernel import IST,Bar
from liquidity.runtime import Store,config
from liquidity.paper import register,records,evaluate_paper,summary

class PaperTests(unittest.TestCase):
    def setup_record(self):
        t=datetime(2026,10,15,10,1,30,tzinfo=IST)
        signal=dict(id='a'*64,symbol='TEST',strategy_id='jadecap_nse_liquidity_v1',decision='BUY',earliest_actionable_time=t.isoformat(),session_date_ist='2026-10-15',entry_reference=100,stop=98,targets=[104])
        return dict(id=signal['id'],symbol='TEST',signal=signal,status='ENTRY_PENDING'),t
    def bar(self,minute=5,h=105,l=99,o=100,c=102):return Bar(datetime(2026,10,15,10,minute,tzinfo=IST),o,h,l,c,100)
    def test_no_entry_before_discovery_and_target(self):
        r,t=self.setup_record();cfg=config()
        b=self.bar();out=evaluate_paper(r,[b],b.t+timedelta(minutes=6,seconds=30),cfg)
        self.assertEqual(out['status'],'CLOSED');self.assertEqual(out['result'],'POSITIVE');self.assertEqual(out['exit_reason'],'TARGET')
        self.assertEqual(out['paper_entry_at'],b.t.isoformat())
        self.assertEqual(evaluate_paper(r,[self.bar(0)],t,cfg)['status'],'ENTRY_PENDING')
    def test_stop_ambiguous_and_gaps(self):
        r,t=self.setup_record();now=t+timedelta(hours=1);cfg=config()
        self.assertEqual(evaluate_paper(r,[self.bar(h=103,l=97)],now,cfg)['result'],'NEGATIVE')
        self.assertEqual(evaluate_paper(r,[self.bar(h=105,l=97)],now,cfg)['status'],'AMBIGUOUS')
        self.assertEqual(evaluate_paper(r,[self.bar(10)],now,cfg)['status'],'DATA_MISSING')
        self.assertEqual(evaluate_paper(r,[self.bar(o=105,c=105,h=106,l=104)],now,cfg)['status'],'MISSED_SETUP')
    def test_ledger_restart_and_zero_statistics(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp:
            st=Store(Path(tmp)/'p.sqlite');self.assertIsNone(summary(st)['positive_rate'])
            r,t=self.setup_record();register(st,r['signal']);register(st,r['signal']);self.assertEqual(len(records(Store(st.path))),1)
            self.assertEqual(summary(st)['pending'],1)

if __name__=='__main__':unittest.main()
