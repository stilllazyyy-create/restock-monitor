# Restock monitor

The active workflow is **Continuous Restock Monitor**:
https://github.com/stilllazyyy-create/restock-monitor/actions/workflows/continuous-monitor.yml

## Check whether it is working

Open `.monitor_health.json` on `main`. `checked_at` is the actual UTC check
time, `interval_seconds` is the configured interval, and the two shop results
show whether the checks succeeded. The store state files also record check
times and the workflow run ID. State is committed after every check, including
when a shop fails. A yellow Running job is expected: one worker checks both
stores repeatedly instead of exiting after a single check.

## How it runs

- Each bounded worker performs ten checks, 300 seconds apart, then requests
  another run using `workflow_dispatch` and the repository `GITHUB_TOKEN`.
- Cron at :17 and :47 provides a backup wake-up. The normal handoff does not
  wait for another cron event. The initial deployment performs two checks
  60 seconds apart to validate the loop and handoff promptly.
- One concurrency group serializes all state writers. The old Chrome Hearts
  and Stussy workflows remain available for manual checks, without schedules.
- Every shop subprocess has a 180-second timeout. A failed shop does not block
  the other shop. Any failed cycle makes the bounded worker report failure,
  and the relay can still retry. Failed state pushes stop the worker.
- No new external account, long-lived token, or hosting service is required.
  Only standard GitHub-hosted Linux runners and the existing Discord secrets
  are used. The workflow token has contents/write and actions/write for state
  commits, dispatching the next run, and the narrowly scoped orphan recovery.

This reduces dependence on the observed multi-hour schedule gaps. It remains
dependent on GitHub's runners and API; it is not an independent hosting service
or a guarantee against outages or delayed runner starts. A slow/failed check
can exceed the five-minute interval. Actual timestamps, not cron syntax, are
the evidence of execution.

To stop monitoring, disable **Continuous Restock Monitor** in Actions, then
cancel its active/pending runs. Disabling the workflow blocks continuation and
the backup schedule. A directly cancelled worker skips the relay step.

## What is monitored

`scripts/chromehearts.py` identifies new categories, new product links, and
product links that return after disappearing. Baccarat, boxers/leggings,
intimates, scents and socks remain tracked but do not generate listing alerts.
Existing history is preserved; deployment does not replay old products.

**A listing change is not verified purchasable stock.** Chrome Hearts does not
yet detect a size restocking when its product URL remains unchanged. No
unverified size parser has been added.

`scripts/stussy.py` uses Shopify's variant IDs and boolean `available` values
for the existing eight size targets and maintains permanent new-arrival history.
Unknown availability or a missing variant preserves the old stock state.
Corrupt state fails visibly instead of silently resetting the baseline.
Notification failures retain retry state; fetch and delivery failures are
recorded in `check_errors` and reported as unsuccessful checks.

Repository Actions secrets:

- `CHROME_HEARTS_WEBHOOK_URL`
- `DISCORD_WEBHOOK_URL`

Do not commit webhook URLs or other credentials. A successful check with no
changes does not send a message and therefore does not verify live Discord
delivery. Delivery success/failure and retry behavior are covered by mocked
tests.

## September 15 orphan

Run `34952449229` (Chrome Hearts Monitor #2099, workflow `340822524`) was
created September 15, 2026, at 09:25:06 UTC and still reports queued with zero
jobs (check suite `94647428518`). It belongs to the old workflow and a different concurrency group.

The recovery step validates that exact run ID, workflow ID, age and zero-job
condition before attempting normal and force cancellation. It never deletes
history or cancels a current monitor. Live run `39986252829` retried both
operations on October 23; both returned HTTP 409:

> Cannot cancel a workflow run that has not been queued yet.

The final API read still reported `queued`. This is **not cleared**. Previous
disable/re-enable attempts also did not clear it. GitHub Support needs to
inspect the internal run/check-suite state. The new worker has demonstrably
started and continued despite this old record. Do not claim the orphan is
the proven cause of every missed scheduled trigger.

GitHub's troubleshooting guidance:
https://docs.github.com/en/enterprise-cloud@latest/actions/how-tos/troubleshoot-workflows#canceling-workflows

## Validation

Run `python3 -m unittest discover -s tests -v` offline. Eleven tests cover
Chrome Hearts partial failures, notification retry, first-run baselines and
deduplication; worker timeout/isolation/continuation; and Stussy delivery
failure, successful delivery state, corrupt state and unknown availability.

The deployment run `39986252829` passed all eleven tests and completed two
real checks at 16:22:47 and 16:23:47 UTC, then successfully dispatched run
`39986429829`. That automatic successor completed its first real check at
16:24:03 UTC with both shops successful and a 300-second polling interval.

The same automatic successor completed its second check at 16:29:03 UTC,
exactly 300 seconds after its first check. Both shops succeeded and both
state files plus the worker heartbeat were persisted. This validates one live
five-minute interval in addition to the automatic handoff, not unlimited future
uptime. These times are 12:24:03 and 12:29:03 in America/Toronto on October 23.
