"""Personal research only. No broker connection, no order execution."""
import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

IST = timezone(timedelta(hours=5, minutes=30))
UNIVERSE_URL = 'https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv'
STRATEGY = 'breakout-ema-volume-v1'
HOLIDAYS_URL = 'https://www.nseindia.com/api/holiday-master?type=trading'


def request(url, payload=None, token=None, method=None):
    headers = {'User-Agent': 'personal-nifty-research/1.0', 'Accept': 'application/vnd.github+json' if token else '*/*'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    req = Request(url, data=json.dumps(payload).encode() if payload is not None else None, headers=headers, method=method)
    with urlopen(req, timeout=40) as response:
        return response.read().decode('utf-8-sig')


def universe():
    raw = request(UNIVERSE_URL)
    rows = list(csv.DictReader(io.StringIO(raw)))
    symbols = [r.get('Symbol', '').strip() for r in rows]
    if len(symbols) != 50 or len(set(symbols)) != 50 or any(not re.fullmatch(r'[A-Z0-9&-]+', s) for s in symbols):
        raise ValueError('UNIVERSE_INVALID: require exactly 50 unique official symbols')
    if any(r.get('Series', '').strip() != 'EQ' for r in rows):
        raise ValueError('UNIVERSE_INVALID: non-EQ constituent')
    return sorted(symbols), hashlib.sha256(raw.encode()).hexdigest()


def holiday_status(now):
    try:
        entries = json.loads(request(HOLIDAYS_URL))['CM']
        dates = [datetime.strptime(x['tradingDate'], '%d-%b-%Y').date() for x in entries]
        if not dates or not any(d.year == now.year for d in dates):
            raise ValueError('calendar year missing')
        return ('HOLIDAY' if now.date() in dates else 'REGULAR_WEEKDAY'), HOLIDAYS_URL
    except Exception:
        return 'UNKNOWN: official calendar unavailable; require current-session bars', HOLIDAYS_URL


def session_bar(t):
    minute = t.hour * 60 + t.minute
    return t.weekday() < 5 and 555 <= minute < 930 and (minute - 555) % 15 == 0 and t.second == 0


def expected_close(now):
    opening = now.replace(hour=9, minute=15, second=0, microsecond=0)
    elapsed = int((now - opening).total_seconds() // 900)
    return min(opening + timedelta(minutes=15 * max(0, elapsed)), opening.replace(hour=15, minute=30))


def clean_bars(frame, now):
    if frame.empty or frame.index.tz is None or frame.index.has_duplicates:
        raise ValueError('EMPTY_OR_INVALID_TIMESTAMPS')
    # Yahoo sometimes includes a zero-volume stub at the beginning of a 1mo query.
    # Use a fixed 250-bar window; malformed bars inside this window still fail closed.
    frame = frame.sort_index().tail(250).copy()
    frame.index = frame.index.tz_convert(IST)
    out = []
    for stamp, row in frame.iterrows():
        t = stamp.to_pydatetime()
        if t > now:
            raise ValueError('FUTURE_TIMESTAMP')
        if not session_bar(t) or t + timedelta(minutes=15, seconds=90) > now:
            continue
        values = [float(row[k]) for k in ['Open', 'High', 'Low', 'Close', 'Volume']]
        o, h, l, c, v = values
        if not all(math.isfinite(x) for x in values) or min(o, h, l, c) <= 0 or v <= 0 or l > min(o, c) or h < max(o, c) or l > h:
            raise ValueError('INVALID_OHLCV')
        out.append(dict(t=t, o=o, h=h, l=l, c=c, v=v))
    return out


def ema(values, span):
    value = values[0]
    for x in values[1:]:
        value += 2 / (span + 1) * (x - value)
    return value


def evaluate(bars, index):
    # 150 bars warm up the EMA50; breakout and volume exclude the signal candle.
    if index < 150:
        return None
    history, b = bars[:index], bars[index]
    recent = history[-20:]
    closes = [x['c'] for x in history] + [b['c']]
    fast, slow = ema(closes, 20), ema(closes, 50)
    volume_ratio = b['v'] / (sum(x['v'] for x in recent) / 20)
    if volume_ratio < 1.5:
        return None
    direction = 'LONG' if b['c'] > max(x['h'] for x in recent) and fast > slow and b['c'] > fast else 'SHORT' if b['c'] < min(x['l'] for x in recent) and fast < slow and b['c'] < fast else None
    if not direction:
        return None
    window = bars[index-13:index+1]
    ranges = [max(x['h']-x['l'], abs(x['h']-bars[index-13+j-1]['c']), abs(x['l']-bars[index-13+j-1]['c'])) for j, x in enumerate(window)]
    atr = sum(ranges) / 14
    risk = max(1.5 * atr, b['c']-b['l'] if direction == 'LONG' else b['h']-b['c'])
    sign = 1 if direction == 'LONG' else -1
    if risk <= 0 or b['c'] - risk <= 0:
        return None
    return dict(direction=direction, reference_close=round(b['c'], 2), stop=round(b['c']-sign*risk, 2), target_2R=round(b['c']+sign*2*risk, 2), atr14_sma=round(atr, 3), volume_ratio=round(volume_ratio, 2), bar_open=b['t'].isoformat(), bar_close=(b['t']+timedelta(minutes=15)).isoformat())


class GitHub:
    def __init__(self):
        self.repo = os.environ['GITHUB_REPOSITORY']
        self.token = os.environ['GH_TOKEN']
        self.base = 'https://api.github.com/repos/' + self.repo

    def api(self, path, payload=None, method=None):
        return json.loads(request(self.base+path, payload, self.token, method))

    def issues(self):
        result = []
        for page in range(1, 1001):
            items = self.api(f'/issues?state=all&per_page=100&page={page}')
            result.extend(x for x in items if 'pull_request' not in x)
            if len(items) < 100:
                return result
        raise RuntimeError('ISSUE_LEDGER_TOO_LARGE')

    def create(self, title, body):
        # Assignment gives the owner an inbox notification without supplying any key.
        return self.api('/issues', dict(title=title, body=body, assignees=[self.repo.split('/')[0]]))

    def health(self, report, issues):
        title = '[NIFTY monitor] Health and coverage'
        item = next((i for i in issues if i['title'] == title), None)
        summary = dict(report, signals_count=len(report['signals']), signals=report['signals'][-10:])
        body = 'Personal research only; execution_authority=false. Full report is in Actions artifacts.\n\n```json\n'+json.dumps(summary, indent=2)+'\n```'
        if item:
            self.api('/issues/'+str(item['number']), dict(body=body), 'PATCH')
        else:
            self.create(title, body)
        # Only notify on a change of health state, not every poll.
        previous = (item or {}).get('body') or ''
        state = report['status']
        if item and f'"status": "{state}"' not in previous:
            self.api('/issues/'+str(item['number'])+'/comments', dict(body='Health changed to **'+state+'**. See issue body for coverage and failures.'))


def scan(now, publish=False):
    report = dict(collected_at=now.isoformat(), source='Yahoo via yfinance; keyless, best effort, personal use', execution_authority=False, status='STARTING', requested=50, evaluated=0, failures={}, signals=[], bars={})
    gh = GitHub() if publish else None
    issues = gh.issues() if gh else []
    try:
        if now.weekday() >= 5 or not (570 <= now.hour*60+now.minute <= 985):
            report['status'] = 'OUTSIDE_POLL_WINDOW'
            return report
        report['calendar_status'], report['calendar_source'] = holiday_status(now)
        if report['calendar_status'] == 'HOLIDAY':
            report['status'] = 'HOLIDAY'
            return report
        # Normal hours only. On holidays no current-date bars -> NO_CURRENT_SESSION_DATA.
        # Never treat missing data as proof that the exchange is on holiday.
        symbols, digest = universe()
        report.update(universe_source=UNIVERSE_URL, universe_sha256=digest, symbols=symbols)
        import yfinance as yf
        for symbol in symbols:
            try:
                frame = None
                for attempt in range(2):
                    try:
                        frame = yf.Ticker(symbol+'.NS').history(period='1mo', interval='15m', auto_adjust=False, actions=True, raise_errors=True, timeout=20)
                        break
                    except Exception:
                        if attempt:
                            raise
                        time.sleep(2)
                bars = clean_bars(frame, now)
                if len(bars) < 151:
                    raise ValueError('INSUFFICIENT_HISTORY')
                today = [i for i, b in enumerate(bars) if b['t'].date() == now.date()]
                if not today:
                    raise ValueError('NO_CURRENT_SESSION_DATA: holiday or unavailable feed')
                latest_end = bars[-1]['t'] + timedelta(minutes=15)
                lag = (expected_close(now)-latest_end).total_seconds()/60
                report['bars'][symbol] = dict(latest_closed=latest_end.isoformat(), lag_minutes=lag)
                if lag > 30 or lag < 0:
                    raise ValueError('STALE_OR_INCONSISTENT_FEED')
                # Missing regular-session bars anywhere in warmup invalidate indicators.
                needed = bars[-175:]
                for a, b in zip(needed, needed[1:]):
                    if a['t'].date() == b['t'].date() and b['t']-a['t'] != timedelta(minutes=15):
                        raise ValueError('MISSING_INTRADAY_BARS')
                for day in sorted({b['t'].date() for b in needed})[1:]:
                    group = [b for b in needed if b['t'].date() == day]
                    if (group[0]['t'].hour, group[0]['t'].minute) != (9, 15):
                        raise ValueError('MISSING_SESSION_OPEN')
                    if day != now.date() and len(group) != 25:
                        raise ValueError('INCOMPLETE_HISTORICAL_SESSION')
                for col in ['Stock Splits', 'Dividends']:
                    if col in frame and (frame[col].fillna(0) != 0).any():
                        raise ValueError('CORPORATE_ACTION_IN_LOOKBACK')
                report['evaluated'] += 1
                # Catch up today after runner delay. Expired signals go to report only.
                for i in today:
                    signal = evaluate(bars, i)
                    if signal:
                        signal.update(symbol=symbol, strategy=STRATEGY)
                        signal['id'] = hashlib.sha256(f"{STRATEGY}|{symbol}|{signal['bar_open']}|{signal['direction']}".encode()).hexdigest()[:24]
                        signal['age_minutes'] = round((now - datetime.fromisoformat(signal['bar_close'])).total_seconds()/60, 1)
                        signal['expired'] = signal['age_minutes'] > 45
                        report['signals'].append(signal)
            except Exception as exc:
                report['failures'][symbol] = str(exc)[:240]
            time.sleep(0.25)
        report['status'] = 'OK' if report['evaluated'] == 50 else 'PARTIAL_COVERAGE' if report['evaluated'] else 'DATA_UNAVAILABLE'
        if gh:
            ledger = {i['title'] for i in issues}
            for signal in report['signals']:
                title = '[NIFTY signal] '+signal['id']
                if not signal['expired'] and title not in ledger:
                    body = '**RESEARCH ONLY — delayed reference levels, not an executable entry. No trades placed.**\n\n```json\n'+json.dumps(signal, indent=2)+'\n```\n\nPartial coverage: '+str(report['evaluated'])+'/50. Yahoo feed and runner may be delayed. Check current prices independently. SHORT is a bearish research signal, not an overnight cash short recommendation.'
                    gh.create(title, body)
                    ledger.add(title)
            report['notifications'] = 'GitHub issue ledger checked; duplicate IDs suppressed'
    except Exception as exc:
        report['status'] = 'FAILED'
        report['error'] = str(exc)[:400]
    finally:
        Path('reports').mkdir(exist_ok=True)
        Path('reports/latest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        if gh:
            gh.health(report, issues)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--publish', action='store_true', help='Write GitHub issues using the automatically provided workflow token')
    parser.add_argument('--now', help='ISO timestamp for read-only replay; cannot publish')
    args = parser.parse_args()
    if args.now and args.publish:
        parser.error('Replay cannot publish')
    now = datetime.fromisoformat(args.now).astimezone(IST) if args.now else datetime.now(IST)
    result = scan(now, args.publish)
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result['status'] in {'FAILED', 'DATA_UNAVAILABLE', 'PARTIAL_COVERAGE'} else 0)
