"""Same-kernel paper experiments. Never promotes a policy or writes live state."""
from collections import Counter
from copy import deepcopy
from datetime import timedelta
from .kernel import evaluate, digest, IST
from .paper import evaluate_paper


def policies(base):
    variants = {}
    for name, window, turtle in (
        ('baseline', base['entry_window'], base['turtle_soup_enabled']),
        ('extended_session', ['09:30', '14:30'], False),
        ('reclaim_confirmation', base['entry_window'], True),
        ('extended_reclaim', ['09:30', '14:30'], True),
    ):
        cfg = deepcopy(base)
        cfg.update(entry_window=list(window), turtle_soup_enabled=turtle,
                   production_enabled=False, notifications_enabled=False,
                   execution_enabled=False)
        variants[name] = cfg
    variants['opening_range_trend'] = dict(deepcopy(base), entry_window=['09:30','14:30'],
        production_enabled=False, notifications_enabled=False, execution_enabled=False)
    return variants


def replay(symbol, frames, as_of, cfg, engine=evaluate):
    """Prefix-only decisions; outcomes exclusively use subsequent observed bars.

    Source quality and price basis are supplied by the active adapter. Revised
    history is not point-in-time certified. Partial sessions are reported.
    """
    bars = frames['5m']
    reasons = Counter()
    trades = []
    seen = set()
    sessions = set()
    usable = set()
    for i, bar in enumerate(bars):
        discovery = bar.t + timedelta(minutes=5, seconds=cfg['finalization_seconds'])
        if discovery > as_of:
            break
        day = str(bar.t.astimezone(IST).date())
        sessions.add(day)
        prefix = dict(frames, **{'5m': bars[:i+1]})
        decision = engine(symbol, discovery, prefix, cfg)
        reason = (decision.get('reason_codes') or [decision['status']])[0]
        reasons[reason] += 1
        if decision['status'] not in ('WARMUP', 'UNAVAILABLE', 'STALE_FEED'):
            usable.add(day)
        if decision['status'] != 'SIGNAL' or decision['id'] in seen:
            continue
        seen.add(decision['id'])
        safe = {k: v for k, v in decision.items() if k not in ('evidence', 'structure_15m_pivots')}
        record = dict(id=decision['id'], symbol=symbol, signal=safe,
                      status='ENTRY_PENDING', result=None, is_paper=True,
                      execution_enabled=False)
        trades.append(evaluate_paper(record, bars[i+1:], as_of, cfg))
    closed = [t for t in trades if t['status'] == 'CLOSED']
    return dict(symbol=symbol, config_hash=digest(cfg), sessions=sorted(sessions),
                usable_sessions=sorted(usable), reasons=dict(reasons),
                prefix_checks=sum(reasons.values()), setups=len(trades),
                closed=len(closed), positive=sum(t['result'] == 'POSITIVE' for t in closed),
                net_r=sum(t['net_r'] for t in closed),
                outcomes=dict(Counter(t['status'] for t in trades)), trades=trades)


def aggregate(rows):
    reasons = Counter()
    outcomes = Counter()
    for row in rows:
        reasons.update(row.get('reasons', {}))
        outcomes.update(row.get('outcomes', {}))
    closed = sum(r.get('closed', 0) for r in rows)
    positive = sum(r.get('positive', 0) for r in rows)
    net_r = sum(r.get('net_r', 0) for r in rows)
    return dict(symbols=len(rows), failures=sum('error' in r for r in rows),
                prefix_checks=sum(r.get('prefix_checks', 0) for r in rows),
                setups=sum(r.get('setups', 0) for r in rows), closed=closed,
                positive=positive, positive_rate=positive/closed if closed else None,
                expectancy_net_r=net_r/closed if closed else None,
                rejection_funnel=dict(reasons), outcomes=dict(outcomes),
                acceptance='RESEARCH_ONLY_NOT_VALIDATED', active_policy_changed=False,
                note='Variants share data: no independent holdout claim or promotion. More signals do not establish better returns.')
