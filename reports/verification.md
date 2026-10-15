# Verification — 2026-10-15, replacement rehearsal

Status: BLOCKED, not READY_FOR_PROD.

- New backend: Python unittest 14/14 pass; compileall pass. Tests include synthetic bullish/bearish FVG, minimum gap, causal pivots, later MSS after reclaim, no reclaim, expiry, future-daily exclusion, staleness, equal-high tolerance, stop/target risk, aware IST, calendar/holiday/special override, invalid/duplicate/gapped bars and fifty-agent restart/outbox isolation. Synthetic fixture thresholds are explicitly overridden only to isolate detector behavior; not production tuning.
- Fifty-actor simulation: eight ticks (400 actor iterations), one injected provider fault isolated, restart dedupe, closed-session transition. This is a short simulation, not a long-duration market soak or proof of latency under load.
- Local real universe rehearsal: fifty current official EQ constituents validated; at 22:26–22:36 IST all fifty MARKET_CLOSED, ready=0, live failed=0, no current market evaluation. Supervisor heartbeat advanced across multiple cycles. Not market-open acceptance.
- HTTP observed: /health 200 with agents=50; /agents/status 200 with fifty entries; /ready 503 by design. /signals 200 with empty array.
- Actual keyless historical replay: fifty requested, 49 streams downloaded plus TCS insufficient post-action session history. All 49 downloaded streams failed eligible-prefix OHLCV quality (opening zero volume); 7,126 evaluated OOS prefixes were rejected. Usable replay coverage 0/50, not 49/50. Examples also contain missing intraday timestamps. No checks waived. No valid paper trades; win rate/PF/expectancy/CI unmeasured. Baseline comparison unavailable until comparable valid historical input exists.
- Frontend: TypeScript check and saved-chart symbol mapping test passed; framework production build passed. Changed source staged, NOT published. New active feed rejects legacy strategy IDs. Live URL still identifies prior deployment, not replacement acceptance.
- Pine: NSE Liquidity v0.1 - VISUAL REHEARSAL compiled and attached on the saved native 5m GRASIM chart, survived reload, and preserved SMA and user drawing. One unique daily tuple request; exact backend parity remains BLOCKED. Legacy Companion v2 removed from active chart. Native export outputs/TradingView-Liquidity-Rehearsal.png shows actual levels/FVGs and NEUTRAL bias, NOT a verified entry signal. Both saved scanner sources were fully read: each uses 25 request contexts and 1.2x volume breakout logic; preserved without mutation.
- Free-host boundary: no verified always-on Railway backend; GitHub cron best effort only. No new purchase. Zero TradingView technical alerts previously observed; no webhook registration claimed.

## Remaining work / exact blockers

1. Resolve permitted complete finalized five-minute OHLCV, corporate-action/tick metadata and special-session notices. Keep failed tickers blocked. An allowed 15m fallback must be independently implemented/tested and visibly degraded; not silently substitute it.
2. Complete 5m/15m fixture parity after the now-completed saved-source audit and native compilation (currently important differences remain). No claim of TradingView tool control.
3. Run actual market-open fifty-agent rehearsal and longer restart/load soak. Execute chronological out-of-sample and legacy baseline on valid comparable data, with costs/ambiguous fills and uncertainty.
4. Notification retry, expiry, delivery-attempt log and remote-ledger crash reconciliation tests pass. Actual delivery and proof of receipt remain gated; current outbox does NOT mean alerts are active.
5. Publish existing dashboard source only after required gates. No new public staging URL invented. Production strategy remains disabled.

Reproducible commands: `python -m unittest -v`; `python -m compileall -q liquidity monitor.py rehearsal.py replay.py`; `python rehearsal.py --serve`; `python replay.py`. Frontend: `node node_modules/typescript/bin/tsc --noEmit`; `node --experimental-strip-types --test tests/symbols.test.mjs`; `node scripts/run-framework.mjs build` from existing Sites checkout.

Cloud rehearsal independently verified: https://github.com/vijaykevat2004-max/AI-TRADE/actions/runs/38775116016 ; commit cd65c886099f2eee11eb9eaaa7fe239b5584d961 ; job 116560637256 logs show 14 tests OK and fifty MARKET_CLOSED actors at 22:41:03 IST. This was a push-triggered run, not proof of natural scheduled execution or 24x7 uptime. Draft PR: https://github.com/vijaykevat2004-max/AI-TRADE/pull/3 . Main legacy scheduler retired at 37f09283d97c0fd51b18a8b6854644a157c452e9.

Extended synthetic soak executed: `python soak.py` completed 53 ticks / 2,650 actor iterations for fifty observable actors; 49 source-success actors advanced watermarks on every tick, one injected fault stayed isolated, an actual SQLite reopen resumed state, duplicate event IDs=0. States included legitimate NO_SETUP, WAIT_CONFIRM and EXPIRED. This remains synthetic, not market performance.
