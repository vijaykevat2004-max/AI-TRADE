# Free personal NIFTY 50 monitor

Signal-only research. `execution_authority=false`. No broker, orders, TradingView alerts, paid service, market-data key or user-generated GitHub token is used.

## What runs

GitHub Actions runs on standard Linux runners on a public repository (currently free). Every 15 minutes on weekdays, UTC 04:07–10:52 is requested; the Python IST gate scans only 09:30–16:25. Effective normal scheduled scan window is 09:37–16:22 IST. Late polls catch the final 15:15–15:30 candle. GitHub cron can queue late or drop jobs. It is not a continuous real-time service or an availability guarantee. Public scheduled workflows are disabled after 60 days without repository activity; inspect Actions periodically and re-enable when required. There is deliberately no artificial keep-alive activity.

## Data and market calendar

- Fresh official constituent CSV is downloaded on each scan. Exactly 50 distinct EQ symbols must validate. No silently stale fallback universe. Symbols are mapped to Yahoo `.NS`; failures are listed individually.
- Official NSE CM holiday endpoint is tried each run. If inaccessible or the year is missing, calendar status is UNKNOWN. In that case a stock must have today's regular-session bars. Previous-day prices are never interpreted as today's session. Holidays with no bars are reported as unavailable, not falsely confirmed as holidays. Weekend and special/Muhurat sessions are not supported.
- Yahoo via yfinance is keyless, unofficial and intended for personal research. It may be delayed, revised, incomplete, blocked or rate-limited. A TradingView delay does not establish Yahoo's delay. Do not redistribute raw data or assume commercial rights. No CAPTCHA or access-control bypass is used.
- 1 month of 15m unadjusted bars is requested; latest 250 bars feed the calculation. At least 150 prior bars warm up EMA50. Prices must be positive and internally consistent; volume must be positive. A malformed bar inside the calculation window blocks that symbol. Splits/dividends in the requested history also block it conservatively.
- Bar timestamps must be aware and unique. Only regular 09:15–15:30 IST bars are used. A candle is eligible 90 seconds after its 15-minute close. Missing bars/session boundaries in recent history block that symbol. Data can lag at most 30 minutes behind the expected last close. Actual bar timestamps and lag are reported; delay is never assumed fixed.

## Signals and levels

LONG: close above the preceding 20 highs, EMA20 > EMA50, close > EMA20. SHORT is the inverse using preceding lows. Both require signal volume >=1.5 times preceding 20-bar average. The signal bar is excluded from breakout and average-volume thresholds. No profitability claim or backtest validation is made. This is a new reconstructed strategy, not a verified exact copy of the old Pine scripts.

Reference = closed-bar close. ATR = simple mean of 14 true ranges. Risk distance = greater of 1.5 ATR and distance to signal-bar low (LONG) / high (SHORT). Stop = reference minus/plus that distance; target = 2R. These are delayed, theoretical reference levels, not entry instructions or fill guarantees. Shorts are bearish research only. Slippage, gaps, costs and position sizing are not modelled.

## Notifications without supplying a key

The workflow's short-lived automatic `github.token` is used with `contents:read` and `issues:write`. You supply no secret. Signals become issues assigned to the repository owner, which creates GitHub inbox notifications. For email/mobile delivery, enable GitHub account notification settings and the GitHub app notifications. Repository **Watch → All Activity** is recommended. Delivery to a device/email is not verified merely by creating an issue.

Each strategy/symbol/candle/direction has a stable ID. Before publishing, the runner reads all open and closed issues; existing IDs suppress repeats. Do not delete or rename signal issues: they are the durable dedup ledger. Runs are serialized. Notifications older than 45 minutes are suppressed; today's expired candidates remain in the report. There is no prior-day catch-up. A network timeout after GitHub accepts a write may leave that run failed; next run reconciles against the ledger.

The **Health and coverage** issue shows last collection time, calendar status, exact failures, latest bar per stock, evaluated count and recent candidates. Its timestamp is the heartbeat: stale timestamp means monitoring has not updated. A green workflow outside polling hours does not prove data coverage. Partial/zero coverage causes a failed workflow while still preserving valid per-stock signals and the report. State changes post comments. Actions failures can notify via GitHub's own notification settings. A provider outage and a holiday can be indistinguishable when the calendar endpoint is unavailable.

## Open and verify

1. Open the repository **Actions → NIFTY 50 personal research monitor → Run workflow**. The initial source push also runs it.
2. Inspect the run, the health issue and `coverage-<run id>` artifact. Confirm requested=50, the evaluated count, failed symbols and bar times. **Deployed** means the workflow exists; **operational full coverage** means a fresh market-hours run evaluated 50/50. Those are separate checks.
3. Open **Issues** and enable owner notifications. A real signal issue proves GitHub accepted a signal; it does not prove email/push delivery. Test notification delivery by observing the assigned health issue in your GitHub inbox.
4. Turn off with Actions → workflow menu → Disable workflow. Remove/close old issues only if you understand the dedup consequences. No PC/browser needs to stay on.

No ZIP is required. Source is directly readable in GitHub or this folder. Local read-only test: install Python 3.12, `pip install -r requirements.txt`, `python -m unittest -v`, then `python monitor.py`. Only GitHub Actions uses `--publish`. Replay uses `--now <aware ISO timestamp>` and cannot publish.

## Sources

- Constituents: https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv
- Holiday endpoint: https://www.nseindia.com/api/holiday-master?type=trading
- yfinance personal-use limitations: https://ranaroussi.github.io/yfinance/
- Schedule delays and inactivity: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- Free public standard runners: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- Notifications: https://docs.github.com/en/subscriptions-and-notifications

## Initial validation (15 October 2026)

Local unit/integration tests passed (8), including 50-symbol synthetic scan, LONG/SHORT levels, no future-bar lookahead, 90-second closed-bar grace, invalid/duplicate universe rejection, holiday/weekend skip and durable notification dedup across repeat runs. Live official CSV validated 50 symbols. Live Yahoo access worked, but the 14:25 IST scan evaluated only 20/50 because missing historical bars and malformed OHLCV blocked the remainder. This is partial coverage, not a validated 50/50 service. See subsequent health report for current results.
