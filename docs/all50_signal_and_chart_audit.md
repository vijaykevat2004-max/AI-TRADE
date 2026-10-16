# All50 signal and chart audit - proposed policy0.2.1

## Fixed live-pipeline defect

The old scheduled runner checked only the newest5m bar on a15minute poll. A confirmation on an intermediate bar could be consumed by the kernel's first-confirmation rule and never reach the paper ledger. Each unseen, non-stale current-session closed prefix is now evaluated causally. Actual discovery time stays the real poll time, not the earlier candle close. Paper entry remains the next full bar after discovery, with chase/missed-entry gates. IDs deduplicate repeated prefixes and restart recovery. A test specifically creates a confirmation on an intermediate candle while the latest candle has no signal, and verifies one outbox event and one paper record across two polls.

Market-hours target cadence is5minutes, offset after finalization; schedules may queue. This remains scheduled execution, not an always-running process. Late stale setups stay rejected. Hourly closed-market preparation and daily/manual research remain separate.

The website signal journal now also reads automatic paper-ledger signals. Production technical-alert gates remain disabled; a paper record no longer depends on a separate notification issue to appear on the website. Historical paper records are not automatically actionable current signals.

## Real retrospective all50 audit

16October2026 at10:56IST:50symbols,950current-session prefixes,1retrospective setup,0risk-ordering/net-R invariant failures. That setup occurred before the current revised policy deployment and before this audit collected the revised source. It is not proof it was observed live, and was not inserted into the live paper journal or sent as a current entry. Source/config/version/hashes and per-symbol reasons are in the local audit report. A retrospective count does not prove profitability or exact historical live availability.

## Native Pine visual source fixes prepared

Changed session-level plots to line-break style with explicit day/session gaps. Opening-range levels display only after three confirmed opening bars. Script-owned risk drawings are cleared on day change and latest-setup replacement by default, with an explicit keep-history input. Object arrays have caps. Labels now say REHEARSAL and explicitly do not claim backend-record equivalence. User-created drawings are not touched by source code.

Native rules remain a separate older visual model: daily history/feed/adjustment, pivot tie behavior, reference pools, reclaim/MSS anchor, targets and tick assumptions differ from the backend. No native parity certificate is claimed. Browser and computer-use runtimes failed to initialize, so the new Pine source has NOT been compiled, applied, reload-verified or visually audited across any of the50native charts. Source inspection and official language docs do not replace TradingView compilation. Previous saved chart continues to use its earlier indicator until browser access is restored and the source applied.

39Python tests passed locally. Full cloud/deployment results require separate run verification. No trades or brokerage orders are placed.
