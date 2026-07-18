# Finy operations units

The files in `deploy/systemd` are reviewed templates, not confirmed production
server configuration. Before installation, compare them with the existing
Gunicorn unit and replace all of these example values:

| Value | Proposed convention |
| --- | --- |
| Application directory | `/srv/finy/app` |
| Virtual-environment Python | `/srv/finy/venv/bin/python` |
| Service user and group | `finy:finy` |
| Environment file | `/etc/finy/finy.env` |
| Runtime lock | `/run/finy/subscription-lifecycle.lock` |

Do not install the timer until the PostgreSQL cutover is complete, a current
database backup exists, and the lifecycle command has passed a manual production
run. Before Live PayFast, validate the actual Gunicorn and lifecycle units,
complete PostgreSQL cutover, take a backup, and follow `DEPLOYMENT.md`.

## Lifecycle behavior

The lifecycle command checks active and past-due Basic subscriptions. A clean
run exits `0`. It continues past an individual malformed record, prints a final
summary, and then exits nonzero if one or more records failed. Unchanged records
are normal and do not cause failure.

The systemd unit is `Type=oneshot`. It also holds a nonblocking `flock` for the
entire command. If another valid run owns the lock, the new invocation logs
`subscription.lifecycle.lock_skipped` and exits `0` without processing anything.
This is a healthy timer overlap, not a lifecycle failure.

The timer runs every 15 minutes with a small randomized delay. Africa/Johannesburg
does not observe daylight-saving changes, but business decisions do not depend on
the scheduler's wall clock: lifecycle code uses timezone-aware Django datetimes.

## Prepare and verify

Edit copies of the unit templates so their account, paths, and environment file
match the real server. The environment file should be owned by `root`, readable
by the Finy group, and never committed:

```bash
sudo chown root:finy /etc/finy/finy.env
sudo chmod 0640 /etc/finy/finy.env
sudo systemd-analyze verify \
  /path/to/finy-subscription-lifecycle.service \
  /path/to/finy-subscription-lifecycle.timer
```

Take a database backup, install the reviewed files, and reload systemd:

```bash
sudo install -o root -g root -m 0644 \
  deploy/systemd/finy-subscription-lifecycle.service \
  /etc/systemd/system/finy-subscription-lifecycle.service
sudo install -o root -g root -m 0644 \
  deploy/systemd/finy-subscription-lifecycle.timer \
  /etc/systemd/system/finy-subscription-lifecycle.timer
sudo systemctl daemon-reload
```

Run the service manually before enabling the timer:

```bash
sudo systemctl start finy-subscription-lifecycle.service
sudo systemctl status finy-subscription-lifecycle.service
sudo journalctl -u finy-subscription-lifecycle.service -n 100 --no-pager
```

A nonzero service result means the command failed globally or one or more
subscriptions were skipped. The summary and sanitized record-level event contain
local subscription IDs and error classes only. Investigate before enabling the
timer.

## Enable and observe

```bash
sudo systemctl enable --now finy-subscription-lifecycle.timer
sudo systemctl list-timers finy-subscription-lifecycle.timer
sudo systemctl status finy-subscription-lifecycle.timer
sudo journalctl -u finy-subscription-lifecycle.service --since today
sudo systemctl show finy-subscription-lifecycle.service \
  -p Result -p ExecMainStatus -p ExecMainStartTimestamp -p ExecMainExitTimestamp
```

`systemctl list-timers` shows the previous and upcoming run. `systemctl show`
identifies the last process result and exit status. Journald contains the safe
started, completed, failed-record, and overlap events.

An external monitor or systemd `OnFailure=` notification unit can be added later.
This stage deliberately does not send operational or billing email.

## Disable or roll back

```bash
sudo systemctl disable --now finy-subscription-lifecycle.timer
sudo systemctl stop finy-subscription-lifecycle.service
sudo systemctl reset-failed finy-subscription-lifecycle.service
```

Disabling the timer prevents future runs. It does not reverse legitimate
past-due transitions or downgrades already committed to the database. Restore a
database only for confirmed corruption and only from a recovery point that will
not discard later user or payment data. Preserve the journal when investigating
a failed rollout.
