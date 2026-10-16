import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from liquidity.provider_gate import ProviderGate


class ProviderGateTests(unittest.TestCase):
    def test_concurrent_cold_start_initializes_once(self):
        gate=ProviderGate(); entered=threading.Event(); release=threading.Event()
        calls=[]
        def first():
            calls.append('first');entered.set();self.assertTrue(release.wait(2));return 1
        def second():
            self.assertTrue(gate.initialized);calls.append('second');return 2
        with ThreadPoolExecutor(2) as pool:
            a=pool.submit(gate.fetch,first);self.assertTrue(entered.wait(2))
            b=pool.submit(gate.fetch,second);release.set()
            self.assertEqual((a.result(),b.result()),(1,2))
        self.assertEqual(calls,['first','second'])

    def test_bounded_lock_retry_and_no_other_error_suppression(self):
        gate=ProviderGate();attempts=[]
        def locked():
            attempts.append(1)
            if len(attempts)<3:raise RuntimeError('database is locked')
            return 'real observed data'
        self.assertEqual(gate.fetch(locked),'real observed data')
        with self.assertRaisesRegex(ValueError,'INVALID_OHLCV'):
            gate.fetch(lambda:(_ for _ in ()).throw(ValueError('INVALID_OHLCV')))
        calls=[]
        def persistent():calls.append(1);raise RuntimeError('database is locked')
        with self.assertRaises(RuntimeError):gate.fetch(persistent)
        self.assertEqual(len(calls),4)  # initial attempt plus three guarded retries
