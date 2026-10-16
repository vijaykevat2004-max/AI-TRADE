# Data and entitlements

|Component|Observed capability|Boundary|
|---|---|---|
|Yahoo/yfinance|Keyless .NS OHLCV, finite intraday retention|Best effort personal research; neither exchange entitlement nor realtime SLA; redistribution permission unverified|
|Nifty Indices CSV|Exactly 50 distinct EQ symbols validated each refresh|Fail closed if unavailable or changed schema|
|NSE holiday API|CM calendar when available|Unknown calendar blocks fresh decisions; special sessions require explicit dated overrides|
|TradingView Basic|Previously 0 technical alerts; 2 chart indicators|No unattended Pine alerts; native feed may differ from Yahoo|
|GitHub Actions|Existing scheduled CLI|Delayed schedules, no 24x7 process guarantee; public repo issue data|
|Private Sites dashboard|Existing deployed frontend, no schedules|Not proof of scanner uptime|

Coverage means all 50 status rows, separately reporting usable bars and reasons; never 50 successful evaluations merely because 50 were attempted. 5m is primary, completed 15m groups are derived only from three contiguous 5m bars. Daily bars must precede session date. Both streams reset after the most recent corporate action; insufficient post-action warmup blocks rather than mixing pre/post-action levels. Production realtime is BLOCKED.
