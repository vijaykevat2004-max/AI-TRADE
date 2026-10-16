# Rehearsal

Python 3.12+: `pip install -r requirements.txt`; `python -m unittest -v`; `python rehearsal.py --serve`. Bind is deliberately local http://127.0.0.1:8765. /health and /agents/status report process and all fifty actors; /ready is 503 until acceptance, /signals contains paper records only. SQLite agent watermarks/outbox survive restart. Four source workers limit concurrency; failures back off independently. Do not expose this unauthenticated local API publicly.

GitHub workflow is a periodic delayed rehearsal, not an always-on process. Cache is best effort persistence (can be evicted); loss restarts warmup. Signals have durable IDs, but no issue dispatcher is enabled before acceptance. Health publishing reuses existing issue, no secrets in records. No notifications are a claim of trading readiness.

`--serve` stays alive on user hardware while running; computer shutdown stops it. No free always-on cloud host is verified. Before production: acquire an allowed dependable source without purchasing; validate tick metadata/calendar special sessions; complete market-open fifty-symbol rehearsal; execute causal synthetic/parity/OOS suite; verify Pine in actual editor. Do not waive gates merely to display fifty successes.
