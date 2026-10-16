import unittest
from copy import deepcopy
from liquidity.runtime import config
from liquidity.experiments import policies, replay, aggregate
import test_liquidity


class ExperimentTests(unittest.TestCase):
    def test_candidates_preserve_risk_and_active_configuration(self):
        base = config(); original = deepcopy(base)
        variants = policies(base)
        variants['extended_session']['entry_window'][1] = '14:00'
        self.assertEqual(base, original)
        for candidate in variants.values():
            for key in ('min_net_rr', 'round_trip_cost_bps', 'slippage_ticks', 'stop_buffer_ticks', 'finalization_seconds'):
                self.assertEqual(candidate[key], base[key])
            self.assertFalse(candidate['execution_enabled'])

    def test_engine_only_receives_confirmed_prefix(self):
        cfg, fixture = test_liquidity.Tests().synthetic()
        observations = []
        def engine(symbol, now, frames, policy):
            self.assertLessEqual(frames['5m'][-1].t.timestamp()+390, now.timestamp())
            observations.append(len(frames['5m']))
            return dict(status='NO_SETUP', reason_codes=['TEST'])
        row = replay('TEST', {'5m': fixture['bars'], '1d': fixture['daily']}, fixture['now'], cfg, engine)
        self.assertEqual(observations, list(range(1, len(fixture['bars'])+1)))
        self.assertEqual(row['setups'], 0)

    def test_empty_and_missing_are_not_wins(self):
        result = aggregate([dict(symbol='X', error='SOURCE_FAILED')])
        self.assertIsNone(result['positive_rate'])
        self.assertEqual(result['failures'], 1)
        self.assertFalse(result['active_policy_changed'])
