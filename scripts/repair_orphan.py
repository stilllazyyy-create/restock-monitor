"""Cancel only the verified September 15 orphan; never delete run history."""
from datetime import datetime, timezone
import json
import os
import urllib.error
import urllib.request

ROOT = 'https://api.github.com/repos/' + os.environ['GITHUB_REPOSITORY']
TOKEN = os.environ['GH_TOKEN']
RUN_ID = 34952449229


def api(path, method='GET'):
    request = urllib.request.Request(ROOT + path, method=method, headers={
        'Authorization': 'Bearer ' + TOKEN,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    })
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


path = f'/actions/runs/{RUN_ID}'
status, run = api(path)
if status != 200:
    raise RuntimeError(f'Cannot inspect orphan: HTTP {status}')
age = (datetime.now(timezone.utc) - datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))).total_seconds()
status, jobs = api(path + '/jobs')
if status != 200:
    raise RuntimeError(f'Cannot inspect orphan jobs: HTTP {status}')
if run['status'] == 'completed':
    print('Old run is already completed:', run['conclusion'])
elif run['workflow_id'] != 340822524 or age < 86400 or jobs['total_count'] != 0:
    raise RuntimeError('Safety stop: old run no longer matches verified zero-job orphan')
else:
    for endpoint in ['cancel', 'force-cancel']:
        status, response = api(path + '/' + endpoint, 'POST')
        print(f'ORPHAN {endpoint}: HTTP {status}; {response.get("message", "accepted")}')
        if status == 202:
            break
    status, final = api(path)
    print('ORPHAN final status:', final.get('status'), final.get('conclusion'))
    if final.get('status') != 'completed':
        print('::warning::GitHub still retains the zero-job orphan. Cancellation is not confirmed; GitHub Support may be required.')
