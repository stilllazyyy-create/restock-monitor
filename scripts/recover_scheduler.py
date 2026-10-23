"""One-time repair of the verified orphaned run and workflow registration."""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

REPOSITORY = 'stilllazyyy-create/restock-monitor'
STALE_RUN_ID = 34952449229
WORKFLOW_ID = 340822524


def api(path, method='GET'):
    request = urllib.request.Request(
        f'https://api.github.com/repos/{REPOSITORY}/actions/{path}',
        data=b'' if method in ('POST', 'PUT') else None,
        method=method,
        headers={
            'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        content = response.read()
        return json.loads(content) if content else None


def cancel_orphan(call=api, sleep=time.sleep):
    run = call(f'runs/{STALE_RUN_ID}')
    if run['status'] == 'completed':
        return 'Old run already completed; no cancellation needed.'
    created = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
    if run['workflow_id'] != WORKFLOW_ID or run['status'] != 'queued':
        raise RuntimeError('Old run identity/status changed; refusing to cancel.')
    if datetime.now(timezone.utc) - created < timedelta(days=1):
        raise RuntimeError('Refusing to cancel a recent run.')

    for endpoint in ('cancel', 'force-cancel'):
        # Force cancellation is attempted only if normal cancellation did not work.
        try:
            call(f'runs/{STALE_RUN_ID}/{endpoint}', 'POST')
        except urllib.error.HTTPError as error:
            if error.code not in (409, 500, 502, 503, 504):
                raise
            print(f'{endpoint}: GitHub returned HTTP {error.code}')
        for _ in range(4):
            sleep(3)
            current = call(f'runs/{STALE_RUN_ID}')
            if current['status'] == 'completed':
                return f'Old run cleared: {current.get("conclusion")}'
    raise RuntimeError('GitHub still reports the old run as queued after both cancellation attempts.')


def reset_schedule(call=api):
    # Always re-enable, including after an ambiguous disable response.
    try:
        call(f'workflows/{WORKFLOW_ID}/disable', 'PUT')
    finally:
        call(f'workflows/{WORKFLOW_ID}/enable', 'PUT')
    workflow = call(f'workflows/{WORKFLOW_ID}')
    if workflow['state'] != 'active':
        raise RuntimeError('Workflow did not return to active state.')
    return 'Scheduled workflow disabled/re-enabled; state confirmed active.'


def main():
    results = []
    errors = []
    for action in (cancel_orphan, reset_schedule):
        try:
            result = action()
            results.append(result)
            print(result)
        except Exception as error:
            detail = f'{action.__name__}: {type(error).__name__}: {error}'
            errors.append(detail)
            print(f'::error::{detail}')
    summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_path:
        with open(summary_path, 'a') as summary:
            summary.write('## Scheduler recovery\n' + '\n'.join('- ' + x for x in results + errors) + '\n')
    if errors:
        raise RuntimeError('Scheduler recovery has unresolved errors; see the step summary.')


if __name__ == '__main__':
    main()
