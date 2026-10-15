"""Shared keyless universe and GitHub transport; legacy evaluator archived on backup branch."""
import os,json,csv,io,re,hashlib
from urllib.request import Request,urlopen
from datetime import datetime,timedelta,timezone
IST=timezone(timedelta(hours=5,minutes=30))
UNIVERSE_URL="https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv"
HOLIDAYS_URL="https://www.nseindia.com/api/holiday-master?type=trading"
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
        previous = (item or {}).get('body') or ''
        try:
            previous_report = json.loads(re.search(r'```json\s*([\s\S]*?)```',previous).group(1))
        except Exception:
            previous_report = {}
        market_keys = ['collected_at','status','requested','evaluated','failures','bars','symbols','calendar_status','universe_sha256']
        last_market = {k:report[k] for k in market_keys if k in report} if 'symbols' in report else previous_report.get('last_market_scan')
        if not last_market and 'symbols' in previous_report:
            last_market = {k:previous_report[k] for k in market_keys if k in previous_report}
        light_signals = [{k:v for k,v in s.items() if k not in {'evidence','evidence_canonical'}} for s in report['signals'][-10:]]
        summary = dict(report, signals_count=len(report['signals']), signals=light_signals, last_market_scan=last_market)
        body = 'Personal research only; execution_authority=false. Full report is in Actions artifacts.\n\n```json\n'+json.dumps(summary, indent=2)+'\n```'
        if item:
            self.api('/issues/'+str(item['number']), dict(body=body), 'PATCH')
        else:
            self.create(title, body)
        # Only notify on a change of health state, not every poll.
        state = report['status']
        if item and f'"status": "{state}"' not in previous:
            self.api('/issues/'+str(item['number'])+'/comments', dict(body='Health changed to **'+state+'**. See issue body for coverage and failures.'))


if __name__ == "__main__":
    raise SystemExit("Legacy monitor disabled. Use python rehearsal.py (research only).")
