# Free research capability comparison

This is a representative engineering comparison, not an exhaustive survey of every bot or a claim that another framework produces profitable NSE signals. Official documentation reviewed 16 October 2026.

| Framework | Documented capability | Relevant gap / implementation here |
|---|---|---|
| Freqtrade | Dedicated lookahead and recursive-analysis tooling | Prefix-only evaluation is now explicitly tested in same-engine experiments. Dedicated indicator-startup sensitivity and a full differential lookahead audit remain pending. Freqtrade is not our NSE data source. |
| QuantConnect / LEAN | Walk-forward optimization on trailing training windows | Our old learning record is too small for validated selection. Keep candidates separate and do not auto-promote. Genuine rolling train/holdout evaluation requires enough independent sessions; this comparison is not such a result. No paid cloud dependency was added. |
| NautilusTrader | Event-driven research/backtesting, portfolio and risk modeling | Reuse our live five-minute kernel in replay with the existing forward-only paper evaluator. We still lack portfolio simulation, verified tick metadata, and tick-level fill evidence. No execution integration was added. |

Sources:
- https://docs.freqtrade.io/en/stable/recursive-analysis/
- https://www.freqtrade.io/en/stable/lookahead-analysis/
- https://www.quantconnect.com/docs/v2/writing-algorithms/optimization/walk-forward-optimization
- https://nautilustrader.io/docs/latest/concepts/overview/

## Implemented comparison

`experiments.py` evaluates a frozen baseline, an extended entry window, earlier reclaim confirmation, their combination, and an independent proposed opening-range trend candidate. The trend model requires a new closed-bar opening-range break, EMA20 and session VWAP agreement, relative volume at least 1.2, an ATR chase cap, a recent-extreme stop, assumed transaction costs, and net reward/risk at least 1.5. Its proposed 2R target is a test rule, not a price forecast. It does not use the liquidity model's restrictive daily breakout bias.

All candidates are shadow-only. The active configuration, risk floors, execution-disabled flags and paper journal are unchanged. Reports show source failures, every prefix rejection, missed/ambiguous entries and actual subsequent observed-bar outcomes. No zero-signal day is described as no opportunities in the entire market. The experiment's first prefixes can lack sufficient history; those stay failures/warmup rather than receive invented context.

The source is bounded, revised history from the current keyless adapter. It does not establish historical point-in-time availability, portfolio returns, years of intraday history, or out-of-sample success. Variant results share the same data and are not independent holdouts. Daily cloud comparisons run on the existing free scheduled runner; this adds no paid vendor or user key. Do not replace the active policy merely because a candidate produces more setups.