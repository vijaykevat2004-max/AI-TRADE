import unittest
from liquidity.learning import research

class LearningTests(unittest.TestCase):
    def test_no_fabricated_learning(self):
        self.assertEqual(research([])['status'],'INSUFFICIENT_DATA')
    def test_holdout_not_used_for_training_and_deduplicated(self):
        rows=[dict(id=str(i),status='CLOSED',net_r=1 if i<100 else -1,signal=dict(earliest_actionable_time=f'{i:04}',decision='BUY')) for i in range(150)]
        a=research(rows+rows);self.assertEqual(a['unique_closed'],150)
        self.assertFalse(a['active_policy_changed']);self.assertEqual(a['holdout'],45)
        self.assertLess(a['holdout_candidate_net_r'],0)
