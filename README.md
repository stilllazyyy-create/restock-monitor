# Restock monitor

## Chrome Hearts

`.github/workflows/chromehearts-v2.yml` runs `scripts/chromehearts.py`.
Set the repository Actions secret `CHROME_HEARTS_WEBHOOK_URL` to the existing
Discord webhook. Never commit webhook URLs or tokens.

The monitor detects new categories, new product links, and product links that
return after disappearing. Existing products form a silent baseline on the first
run. Baccarat, boxers/leggings, intimates, scents and socks remain tracked but do
not generate listing alerts, matching the requested exclusions.

**Listing presence is not proof of purchasable stock.** The current scraper does
not detect a size becoming available when the product URL remains on the page.
Alerts identify listing changes and should not be described as verified stock.

### Reliability changes

- A failed category retains its last good product list. Other successful
  categories can still notify and save their changes.
- Failed new categories are not absorbed into history before a successful fetch.
- Discord errors stop the state update so detected products can be retried.
- Corrupt state fails visibly instead of silently resetting the notification baseline.
- `last_check_at`, `last_complete_check_at`, and `failed_categories` record health
  in `.chromehearts_state.json`; Actions also displays a check summary.
- The state-save step runs after a partial check, while the job still reports the
  failure. A failure before state is written leaves the previous file unchanged.

### Scheduling limitation found on 2026-10-23

The configured cron is `2-59/5 * * * *`, but the public Actions run history showed
Chrome Hearts scheduled runs at 04:10, 09:20 and 14:18 UTC on October 23 (roughly
five-hour gaps). This is based on workflow run timestamps, not state commits.
The cause of those scheduling gaps has not been established.

Changing the cron alone does not establish that the monitor runs every five
minutes. A fast drop can appear and sell out entirely between executions. For
reliable frequent checks, use an always-running worker or an independent
scheduler with measured execution intervals. This patch does not provision or
deploy such infrastructure and does not claim to fix scheduling delays.

### Checks

Run `python3 -m unittest discover -s tests -v` without network access or Discord
messages. The tests mock both the shop and webhook, including partial shop
failures, notification failures, recovery, deduplication, and first-run baselines.

A real end-to-end Discord test and live workflow verification are still needed
after deploying changes. Existing Stussy configuration is unchanged.

### Scheduler investigation and recovery (2026-10-23)

Run #2099 (`34952449229`), created September 15, still showed `queued` with
zero jobs on October 23. This is a confirmed orphaned-run anomaly, but it does
not prove the cause of the later scheduling slowdown: successful runs continued
after it, and Stussy's separate workflow also slowed down.

Pagination of the history localizes the abrupt slowdown to September 22, after
Chrome Hearts run #2841 at 08:57 UTC. Recent successful executions take about
10–15 seconds; most adjacent run numbers are consecutive, so the hours-long
gaps are largely missing triggers, not long-running script execution.

Recovery changes shift cron to `3-58/5 * * * *` (still five minutes) to refresh
registration and move the concurrency group to `chrome-hearts-monitor-v2` to
isolate old queue state. The one-time recovery workflow attempts normal, then
force cancellation of only the verified, over-one-day-old queued run. It also
disables and re-enables workflow `340822524`, always attempting re-enable, and
checks that it is active afterward. It does not cancel current monitor runs.

Actual check gaps are recorded as `previous_check_gap_seconds`. Gaps longer
than 15 minutes produce an Actions warning. A successful push-triggered test
does not validate cron timing; scheduled runs must be measured separately.

The internal GitHub cause cannot be established from these API records alone.
Do not describe this recovery as proven until scheduled intervals improve.

### Recovery outcome and clean workflow registration

The live recovery run `39972226765` confirmed that both normal cancellation and
force cancellation return HTTP 409 for orphaned run `34952449229`. It still has
no jobs and remains queued. Disable/re-enable succeeded and the original workflow
was confirmed active, but did not clear this orphan. GitHub's troubleshooting
documentation identifies this pattern as potentially requiring GitHub Support.

To avoid relying on the affected workflow registration, the active monitor is
now `.github/workflows/chromehearts-v2.yml` named `Chrome Hearts Monitor v2`. The
old workflow file and the temporary recovery workflow were removed. The new
entry uses a separate concurrency group and keeps the existing product state and
Discord secret. It does not replay existing products as a fresh baseline.

The old anomalous record remains available for investigation. A new workflow is
a recovery measure, not proof that the orphan alone caused every missing trigger.
`workflow_run_id` and `workflow_event` in state identify whether each observed
check actually came from the scheduler or a code push.

### Continuous worker deployed October 23

The active workflow is now `.github/workflows/continuous-monitor.yml`.
It checks Chrome Hearts and Stussy in the same serialized worker every 300
seconds, for ten checks, then requests the next worker with workflow_dispatch.
Cron at :17 and :47 is a backup wake-up. This reduces dependence on the
observed hours-long gaps between schedule events; it is not an independent
hosting service or a guarantee against GitHub runner outages/delays.
The deployment push performs two checks 60 seconds apart to validate the loop.

Each cycle commits both store state files and `.monitor_health.json`, including
the real check time, result per shop, event, and run ID. Checks have a 180-second
per-shop timeout; a failed shop does not prevent checking the other. A failed
cycle causes a failed job after the bounded worker finishes, and the handoff
still runs. State-push failures abort the worker to avoid silently losing
notification history. Stussy now preserves unknown availability and corrupt
state, records fetch/delivery failures, and retains failed alerts for retry.

The two original workflows remain available for manual checks and share the
worker concurrency group. Their schedules have been removed to avoid competing
state writers. The unused nested workflow and diagnostic probe were removed.

To stop continuous monitoring, disable **Continuous Restock Monitor** in
Actions and cancel its active/pending runs. Disabling it blocks both dispatch
continuation and the backup schedule. A direct cancellation skips the relay step.
The worker uses the existing repository Discord secrets; no new tokens or
external services are required. Standard hosted Linux runners are used.

The deployment also retries normal and force cancellation of only the verified
September 15 zero-job orphan `34952449229` (workflow `340822524`). It does not
delete logs/history or cancel current workers. Its live output reports whether
GitHub accepted either cancellation. If both return 409 and the run remains
queued, this is not locally resolved; GitHub Support must inspect the run's
internal state. Do not claim removing unrelated workflow files clears that run.

Chrome Hearts still identifies listing/category changes, not verified size
availability on an unchanged product page. No unverified stock parser has been
added. A successful empty-check run also does not verify Discord delivery;
delivery-failure/retry logic is covered by mocked tests.
