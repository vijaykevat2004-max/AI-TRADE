# NIFTY signal system: implementation and acceptance

## Intended experience

Cloud scans all 50 constituents; publishes only qualifying research signals. Opening a stock should show the signal candle and reference entry, stop and target. The user specifically wants these markings in their real TradingView account. A separate chart is supporting evidence, not a substitute for that acceptance condition.

## Components implemented

1. Existing GitHub Actions runner: fresh official 50-symbol universe, 15m closed bars, IST hours, official holiday lookup, no-current-session guard, data integrity checks, EMA/breakout/volume logic, reference risk levels, retry and 5m recovery, serialized runs, durable issue dedup, failure reports.
2. Frozen evidence for newly created candidates: 41 actual bars, preceding high/low and volume threshold, EMA values and seeds, source/collection time, canonical JSON and SHA-256 digest. A digest checks consistency; it is not independent exchange certification. Existing earlier signals lack these snapshots and remain labelled accordingly.
3. Private dashboard: https://nifty-signal-command-centre.vijaykevat2004.chatgpt.site . Reads actual bot-authored GitHub evidence; current-source chart via a keyless Yahoo request; selected signal's original snapshot takes precedence when available. No fabricated candles, no fabricated signals. Historical/expired signals are labelled. Each stock has a TradingView link using the user's saved chart layout and 15m interval. It never claims that a link imports backend drawings.
4. TradingView companion Pine indicator: native chart EMA20/50, confirmed 15m breakout/volume signals, labels and reference/stop/target lines. It uses TradingView's own feed and may disagree with Yahoo. Saved native overlay is a chart feature, not a TradingView cloud scanning service.
5. Explicit after-hours source audit: scans the current date and writes health evidence without sending signal alerts. Previous market scan is retained in the health issue when normal polls are outside market hours.

## Data path

Official NIFTY CSV → keyless Yahoo/yfinance → validated candles → deterministic signal + snapshot → GitHub issue/notification → private dashboard → selected chart + evidence → native TradingView chart link.

TradingView companion: TradingView's own chart data → native Pine calculations → chart labels/lines. This is a separate computation, not an import of the cloud snapshot. No TradingView scraping, private API, session export, CAPTCHA bypass or broker connection is implemented.

## Acceptance ledger

- Scheduled source exists and initial cloud execution/issue assignment were verified. A naturally scheduled market-hours occurrence must be verified separately.
- Every run requests 50 constituents; source failures are explicit. Full 50/50 usable coverage has not been demonstrated.
- 10 local backend tests pass, including repeat-run dedup, no-lookahead, exact candle closure, holiday skip, real-group 5m recovery and snapshot digest consistency.
- Dashboard type checking and production build pass. Real preview chart/source/GRASIM reference levels have been visually checked.
- TradingView Pine must compile, attach within Basic plan limits, save to layout, survive reload, and show native lines. Each of these requires fresh UI verification before claiming it.
- Backend and TradingView signal equality is not guaranteed across different feeds and is not certified. A system with full autonomous access to all TradingView tools is not implemented.
- No order placement. Reference close is not an execution/fill. No expected profitability, accuracy percentage or live-entry recommendation is claimed.

## Operating boundaries

GitHub cron is best effort and may be disabled after inactivity. Railway could host a future continuous worker, but no paid deployment, credit commitment, browser session export or resource budget has been authorized or provisioned. Railway is not necessary for the current scheduled backend. No forever-free or uninterrupted service promise.

Yahoo is unofficial, personal-use and may delay or omit data. Automatic data recovery never fabricates OHLCV. NSE normal sessions only; special/weekend sessions are unsupported. Calendar failure is UNKNOWN, not proof of a holiday.

Dashboard data reads can be rate-limited; caches are two minutes. Recent history is limited to the newest 500 GitHub issues, explicitly surfaced by the API. Original records stay in GitHub; owner-created edits can change them. Do not delete/rename signal ledger issues.
