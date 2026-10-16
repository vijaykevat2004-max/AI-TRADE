"""Free bounded all-50 strategy comparison; no live policy mutation."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import argparse
import json
from liquidity.kernel import IST, digest
from liquidity.runtime import config, source
from liquidity.experiments import policies, replay, aggregate
from liquidity.kernel import evaluate
from liquidity.trend_candidate import evaluate_trend
from monitor import universe, GitHub


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbols', nargs='*')
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    now = datetime.now(IST)
    symbols, manifest = universe()
    if args.symbols:
        if any(s not in symbols for s in args.symbols):
            raise ValueError('OUTSIDE_VALIDATED_UNIVERSE')
        symbols = args.symbols
    variants = policies(config())
    def inspect(symbol):
        try:
            frames = source(symbol, now, config())
            return {name: replay(symbol, frames, now, cfg, evaluate_trend if name=='opening_range_trend' else evaluate) for name, cfg in variants.items()}
        except Exception as exc:
            return {name: dict(symbol=symbol, error=str(exc)[:200]) for name in variants}
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(inspect, symbols))
    results = {name: [r[name] for r in rows] for name in variants}
    summaries = {name: aggregate(value) for name, value in results.items()}
    report = dict(collected_at=now.isoformat(), requested=len(symbols),
                  universe_hash=manifest, active_config_hash=digest(config()),
                  mode='SAME_5M_KERNEL_SHADOW_COMPARISON', execution_enabled=False,
                  active_policy_changed=False, summaries=summaries, results=results,
                  limitations=['Best-effort revised source; not point-in-time evidence',
                               'Bounded available history; no years claim',
                               'No independent holdout or auto-promotion',
                               'Overlapping hypothetical setups are not a portfolio return'])
    Path('reports').mkdir(exist_ok=True)
    Path('reports/experiments.json').write_text(json.dumps(report, indent=2, default=str))
    if args.publish:
        gh = GitHub()
        title = '[NIFTY experiments] Same-engine strategy comparison'
        public = {k: v for k, v in report.items() if k != 'results'}
        body = 'Hypothetical research only. No live policy promotion or orders.\n\n```json\n' + json.dumps(public, indent=2) + '\n```'
        old = next((i for i in gh.issues() if i['title'] == title), None)
        if old:
            gh.api('/issues/' + str(old['number']), dict(body=body), 'PATCH')
        else:
            gh.api('/issues', dict(title=title, body=body))
    print(json.dumps(summaries))


if __name__ == '__main__':
    main()
