# Existing project audit — 2026-10-15

Repository: https://github.com/vijaykevat2004-max/AI-TRADE ; inspected main 14256fcaddb7db2d50d6cd47725fdac3ec668ab3. Clean clone before changes. Backup: backup/legacy-momentum-20261015. Implementation: feat/jadecap-nse-liquidity-v1.

Active CLI monitor.py uses EMA20/50, 20-bar breakout, 1.5 relative volume, 15m candles; no liquidity strategy. GitHub Actions polls every 15 minutes; no always-on server, database or fifty persistent actors. Dependencies: Python, yfinance, pandas, tzdata. GitHub automatic workflow token writes Issues. No broker integration. Legacy health issue /issues/2 and signal /issues/1 must remain historical records.

Existing frontend is a separate private Sites source checkout ../nifty-command-centre (31c03ace6b92d4c88210dab35275612e93497ded), Vinext/React on Sites, not Vercel. Account lookup confirms active https://nifty-signal-command-centre.vijaykevat2004.chatgpt.site and no Sites schedules. Existing /api/status consumes GitHub issue JSON; /api/chart requests Yahoo 15m. No Railway configuration or authenticated running Railway service was discovered. Do not infer one.

Previously observed TradingView account vijayxraw Basic: two chart indicators, zero technical alerts, delayed NSE feed. Saved layout https://www.tradingview.com/chart/mWisj3X4/ . Companion v2 is legacy momentum. Two saved 25-stock reconstructed scanners were deployed earlier; their full source has NOT been re-audited in this replacement. Do not modify those scripts or claim new Pine compilation until examined and actually compiled.

Production replacement gates: permitted reliable intraday feed; validated calendar; fifty-symbol market-open rehearsal; causal parity and OOS replay; actual always-on hosting. Not satisfied at audit. New code defaults to rehearsal, never execution. No new service purchase or credentials required for local replay.
