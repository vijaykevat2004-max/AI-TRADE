# JadeCap NSE liquidity replacement — delayed rehearsal only

Existing repository and account retained. **PRODUCTION BLOCKED**: no dependable 50-stock 5m feed, market-open rehearsal or Pine/backend parity has passed. No broker or order interface exists. execution_enabled=false.

Strategy: jadecap_nse_liquidity_v1 / 0.1.0. The TradeZella idea and the proposed deterministic NSE rules are separated in docs/strategy_source_vs_proposal.md. Start with docs/as_is_audit.md and reports/verification.md.

## Run

Python 3.12+: `pip install -r requirements.txt`; `python -m unittest -v`; `python rehearsal.py --serve`. Local API http://127.0.0.1:8765: /health, /agents/status, /signals; /ready deliberately 503. `python replay.py` downloads real historical source data for a read-only chronological audit, never alerts. No market-data API key is requested.

Fifty isolated logical actors share a bounded four-worker supervisor. SQLite keeps their state and deduplicated outbox. Closed exchange reports fifty MARKET_CLOSED actors without fetching invented current bars. Calendar unavailable during market hours fails closed. Cash hours are 09:15–15:30 IST, the experimental setup window is 09:30–11:30. Special-session overrides require notice verification.

GitHub workflow requests periodic rehearsal runs and publishes health only using its automatic token. This is not a 24x7 cloud process; schedules and caches can be delayed/evicted. The durable retry/expiry/ledger notification dispatcher is implemented and disabled until acceptance. Legacy Issues remain historical. Backup branch backup/legacy-momentum-20261015 preserves the old strategy; main legacy schedule was retired separately.

Existing private dashboard: https://nifty-signal-command-centre.vijaykevat2004.chatgpt.site . This URL identifies the existing deployed legacy frontend, NOT a verified replacement release. Replacement source is staged in the existing Sites checkout; publication waits for acceptance. Existing TradingView layout: https://www.tradingview.com/chart/mWisj3X4/ . Pine source is a visual rehearsal candidate and has no cloud alert entitlement or certified parity.

## Source limitations

Yahoo/yfinance is unofficial keyless best effort, not an exchange entitlement or a realtime SLA. Three recent intraday sessions and up to sixty completed daily bars are used. Both streams reset after the latest corporate action in used daily history; insufficient post-action warmup blocks that stock. Strict positive OHLCV, chronological unique timestamps, finalized candles and intraday gap checks apply. No synthetic fills, invented volume or control bypass. Tick metadata and special-session audit remain production blockers. A full OHLCV entitlement/redistribution review is still required for anything beyond personal research.

The fifteen-minute structure is derived from complete contiguous five-minute triples and recorded as context; an independently backtested 15m structural eligibility filter and DEGRADED_15M fallback are NOT enabled. There is no RSI divergence module. Breaker, continuation and the conflicting source 1h example are disabled.

No claimed win rate, uptime, profitability or complete source coverage. See the verification report for exact measured failures.
