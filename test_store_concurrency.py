import tempfile,unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from liquidity.runtime import Store

class StoreConcurrencyTests(unittest.TestCase):
    def test_distinct_store_handles_share_gate_and_preserve_fifty_writes(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp:
            path=Path(tmp)/'s.sqlite';first=Store(path);second=Store(path)
            self.assertIs(first._lock,second._lock)
            def task(i):
                handle=first if i%2 else second
                for j in range(4):
                    # Exercise the read-to-write upgrade pattern across handles.
                    with handle.connect() as db:
                        db.execute('SELECT COUNT(*) FROM agents').fetchone()
                        db.execute('INSERT OR REPLACE INTO agents VALUES(?,?)',('S'+str(i),'{}'))
                    handle.states()
            with ThreadPoolExecutor(max_workers=12) as pool:list(pool.map(task,range(50)))
            self.assertEqual(len(first.states()),50)
            with first.connect() as db:self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
