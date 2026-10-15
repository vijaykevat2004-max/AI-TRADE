# Verification — 2026-10-15, replacement rehearsal

Status: BLOCKED, not READY_FOR_PROD.

- New backend: Python unittest 14/14 pass; compileall pass. Tests include synthetic bullish/bearish FVG, minimum gap, causal pivots, later MSS after reclaim, no reclaim, expiry, future-daily exclusion, staleness, equal-high tolerance, stop/target risk, aware IST, calendar/holiday/special override, invalid/duplicate/gapped bars and fifty-agent restart/outbox isolation. Synthetic fixture thresholds are explicitly overridden only to isolate detector behavior; not production tuning.
- Fifty-actor simulation: eight ticks (400 actor iterations), one injected provider fault isolated, restart dedupe, closed-session transition. This is a short simulation, not a long-duration market soak or proof of latency under load.
- Local real universe rehearsal: fifty current official EQ constituents validated; at 22:26–22:36 IST all fifty MARKET_CLOSED, ready=0, live failed=0, no current market evaluation. Supervisor heartbeat advanced across multiple cycles. Not market-open acceptance.
- HTTP observed: /health 200 with agents=50; /agents/status 200 with fifty entries; /ready 503 by design. /signals still requires final verification.
- Actual keyless historical replay: fifty requested, 49 streams downloaded plus TCS insufficient post-action session history. All 49 downloaded streams failed eligible-prefix OHLCV quality (opening zero volume); 7,126 evaluated OOS prefixes were rejected. Usable replay coverage 0/50, not 49/50. Examples also contain missing intraday timestamps. No checks waived. No valid paper trades; win rate/PF/expectancy/CI unmeasured. Baseline comparison unavailable until comparable valid historical input exists.
- Frontend: TypeScript check and saved-chart symbol mapping test passed; framework production build passed. Changed source staged, NOT published. New active feed rejects legacy strategy IDs. Live URL still identifies prior deployment, not replacement acceptance.
- Pine: candidate source has one unique request.security tuple; NOT yet compiled/installed or parity-certified. Existing chart was freshly observed with legacy Companion v2 and NSE_DLY data. Two saved scanners are not newly certified.
- Free-host boundary: no verified always-on Railway backend; GitHub cron best effort only. No new purchase. Zero TradingView technical alerts previously observed; no webhook registration claimed.

## Remaining work / exact blockers

1. Resolve permitted complete finalized five-minute OHLCV, corporate-action/tick metadata and special-session notices. Keep failed tickers blocked. An allowed 15m fallback must be independently implemented/tested and visibly degraded; not silently substitute it.
2. Complete Pine source audit, native editor compilation, 5m/15m fixture parity (currently important differences remain). No claim of TradingView tool control.
3. Run actual market-open fifty-agent rehearsal and longer restart/load soak. Execute chronological out-of-sample and legacy baseline on valid comparable data, with costs/ambiguous fills and uncertainty.
4. Notification retry, expiry, delivery-attempt log and remote-ledger crash reconciliation tests pass. Actual delivery and proof of receipt remain gated; current outbox does NOT mean alerts are active.
5. Publish existing dashboard source only after required gates. No new public staging URL invented. Production strategy remains disabled.

Reproducible commands: `python -m unittest -v`; `python -m compileall -q liquidity monitor.py rehearsal.py replay.py`; `python rehearsal.py --serve`; `python replay.py`. Frontend: `node node_modules/typescript/bin/tsc --noEmit`; `node --experimental-strip-types --test tests/symbols.test.mjs`; `node scripts/run-framework.mjs build` from existing Sites checkout.
