# Restock monitor

## Chrome Hearts

`.github/workflows/chromehearts.yml` runs `scripts/chromehearts.py`.
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
