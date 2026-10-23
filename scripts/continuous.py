"""Bounded worker: poll both stores, persist each check, then let Actions relay."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

STATE_FILES = ['.chromehearts_state.json', '.restock_state.json', '.monitor_health.json']


def run_check(script):
    try:
        result = subprocess.run([sys.executable, script], timeout=180)
        return {'ok': result.returncode == 0, 'exit_code': result.returncode}
    except subprocess.TimeoutExpired:
        print(f'::error::{script} exceeded 180 seconds', flush=True)
        return {'ok': False, 'error': 'timeout'}


def persist():
    subprocess.run(['git', 'add', '--', *[p for p in STATE_FILES if Path(p).exists()]], check=True)
    if subprocess.run(['git', 'diff', '--cached', '--quiet']).returncode == 0:
        return
    subprocess.run(['git', 'commit', '-m', 'Record restock checks and worker heartbeat'], check=True)
    for attempt in range(3):
        if subprocess.run(['git', 'push', 'origin', 'HEAD:main']).returncode == 0:
            return
        subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'], check=True)
        time.sleep(3)
    raise RuntimeError('Could not persist monitor state after three pushes')


def main():
    checks = int(os.environ.get('MONITOR_CHECKS', '10'))
    interval = int(os.environ.get('MONITOR_INTERVAL', '300'))
    if not 1 <= checks <= 10 or not 60 <= interval <= 300:
        raise ValueError('Worker bounds: 1–10 checks, 60–300 seconds')
    any_failure = False
    for cycle in range(checks):
        started = time.monotonic()
        now = datetime.now(timezone.utc).isoformat()
        print(f'CHECK {cycle + 1}/{checks} at {now}', flush=True)
        # One shop failing must not suppress the other shop.
        health = {
            'checked_at': now,
            'workflow_run_id': os.environ.get('GITHUB_RUN_ID'),
            'workflow_event': os.environ.get('GITHUB_EVENT_NAME'),
            'cycle': cycle + 1,
            'interval_seconds': interval,
            'chrome_hearts': run_check('scripts/chromehearts.py'),
            'stussy': run_check('scripts/stussy.py'),
        }
        Path('.monitor_health.json').write_text(json.dumps(health, indent=2) + '\n')
        persist()
        if not all(health[s]['ok'] for s in ['chrome_hearts', 'stussy']):
            any_failure = True
            print('::error::A shop check failed; state and failure were recorded; retry next cycle.', flush=True)
        if cycle + 1 < checks:
            time.sleep(max(0, interval - (time.monotonic() - started)))
    if any_failure:
        raise RuntimeError('One or more shop checks failed; see heartbeat and logs. Next worker may retry.')


if __name__ == '__main__':
    main()
