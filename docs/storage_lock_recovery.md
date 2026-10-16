# ASIANPAINT unavailable: storage recovery

The10:59main run reported ASIANPAINT unavailable with database-is-locked. This is a worker storage failure, not a trading setup rejection or proof the native TradingView symbol is unavailable.

The earlier fix protected history's read-to-write upgrade, but actor, paper, outbox and other Store callers could still overlap. Store connections now share a process-wide reentrant gate per resolved database path, including distinct Store instances. Network fetching and calculation remain parallel. SQLite uses WAL mode and a30second busy timeout for other processes. Database operations contain no network requests. This serializes local database access instead of merely hiding a fault or renaming its status.

40Python tests passed, including50writers/readers through distinct Store handles, integrity_check,50adjusted workers, restart recovery and paper-event deduplication. A real local all50run completed with no unavailable stocks. Fresh cloud verification and exact code revision are required separately; local dirty working-tree checks are explicitly marked in the report.

TradingView native markings remain a separate incomplete task. The new Pine visual cleanup is prepared and publicly downloadable, but unavailable browser-control runtimes prevent applying/compiling/reloading it. No claim that account markings were fixed follows from storage recovery.
