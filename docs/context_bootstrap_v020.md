# Proposed research policy 0.2.0: historical bootstrap and coherent adjustment basis

This explicitly revises the engineering context policy. It is not an unchanged source strategy, a validated profitability improvement or native TradingView parity certification. Signal thresholds, risk rules and closed-bar finalization remain unchanged.

## Contiguous historical bootstrap

The most recent eligible prior-session contiguous segment of at least20 valid5m bars seeds pivots and ATR. Only one observed uninterrupted segment is selected. Invalid bars and missing timestamps split segments; no prices are inserted across gaps. The complete current session is appended unchanged and must still pass gap, opening, OHLCV, freshness and closure gates. Daily previous-session extrema still come from completed daily history. Missing trailing bars of an older session are outside the selected segment, not represented as a complete historical session. This bounded-context choice can produce different pivots and signals from the earlier reset-to-latest-suffix policy.

## Corporate-action basis

Instead of discarding months of daily data after every cash dividend, use the provider's explicit AdjClose/Close ratio. All four daily OHLC values are scaled by that reported ratio. Historical intraday OHLC for each date use the SAME dated ratio; today's raw intraday bars retain factor1. Missing, nonfinite or nonpositive factors fail closed. Reported volume is not invented or scaled for cash dividends. Actual stock splits still restrict intraday context to the effective regime. Provider history is revised best-effort data, not independently certified point-in-time exchange data.

Official implementation reference: https://github.com/ranaroussi/yfinance/blob/main/yfinance/utils.py function auto_adjust. This live basis is not silently applied to the separate old15m historical replay, which remains separately labelled; no historical performance equivalence is claimed.

## Persistent cache coherence

When any overlapping dated adjustment factor changes, discard that symbol's incompatible cached history and rebuild from observed source bars. Added new dates alone do not invalidate unchanged overlap. Fresh adjusted daily snapshots are never merged with an older unadjusted or differently adjusted daily basis. Cached bars cannot bypass today's invalid bar or a corporate-action regime.

When a recent completed daily date is missing, retrieve the exact uncompressed official NSE security bhavcopy CSV. Validate symbol, EQ series, date and OHLCV. A missing adjustment factor can be bridged only when the immediately bracketing observed provider factors agree and official PREV_CLOSE matches the prior provider raw close within the configured tick tolerance. Conflicting factors, mismatched previous close, duplicate records or unavailable CSV remain blocked. Official OHLCV is used exactly; no price interpolation. Record CSV URL, checksum, date and adjustment provenance. This bridge inherits provider adjustment uncertainty and is not independent corporate-action certification.

37tests pass, including matching daily/intraday factors, unchanged current raw prices, preservation of current gaps, historical-segment separation, adjusted-cache invalidation, official daily recovery/date/duplicate/conflict rejection, prior source recovery and off-hours non-execution. Local16October10:25IST run observed50/50 current feeds, evaluated50/50 strategy contexts and0warmup. Cloud verification remains separate. The website remains signal/paper only; no orders, no guaranteed uptime, no guaranteed signal frequency or accuracy.
