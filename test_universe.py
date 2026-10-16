import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from monitor import universe,parse_universe,UNIVERSE_EVIDENCE,UNIVERSE_URLS

def fixture(n=50):
    return 'Symbol,Series\n'+''.join(f'S{i},EQ\n' for i in range(n))

class UniverseTests(unittest.TestCase):
    def test_official_archive_recovers_denied_primary(self):
        with patch('monitor.request',side_effect=[HTTPError(UNIVERSE_URLS[0],403,'Forbidden',None,None),fixture()]) as fetch:
            symbols,sha=universe()
        self.assertEqual(len(symbols),50);self.assertEqual(len(sha),64)
        self.assertEqual(fetch.call_count,2);self.assertEqual(UNIVERSE_EVIDENCE['source'],UNIVERSE_URLS[1])
    def test_invalid_csv_cannot_become_coverage(self):
        for raw in (fixture(49),fixture().replace('S49','S0'),fixture().replace('S49,EQ','S49,BE'),'<html>Denied</html>'):
            with self.assertRaises(ValueError):parse_universe(raw)
    def test_total_failure_clears_prior_evidence(self):
        with patch('monitor.request',return_value=fixture()):universe()
        with patch('monitor.request',side_effect=OSError('offline')):
            with self.assertRaisesRegex(RuntimeError,'UNIVERSE_UNAVAILABLE'):universe()
        self.assertEqual(UNIVERSE_EVIDENCE['status'],'UNAVAILABLE')
        self.assertNotIn('source',UNIVERSE_EVIDENCE)
