"""Serialize provider cold-start caches and narrowly retry transient DB contention."""
import threading


class ProviderGate:
    def __init__(self):
        self.lock=threading.Lock()
        self.initialized=False

    def fetch(self, callback):
        # yfinance has its own cookie/timezone SQLite caches, separate from our
        # Store. Only one request may initialize them in a fresh runner.
        if not self.initialized:
            with self.lock:
                if not self.initialized:
                    value=self._retry(callback)
                    self.initialized=True
                    return value
        try:
            return callback()
        except Exception as exc:
            if 'database is locked' not in str(exc).lower():
                raise
            with self.lock:
                return self._retry(callback)

    @staticmethod
    def _retry(callback):
        for attempt in range(3):
            try:
                return callback()
            except Exception as exc:
                if 'database is locked' not in str(exc).lower() or attempt==2:
                    raise
