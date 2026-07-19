# Finy deployment

## PayFast Live and HTTPS readiness

Complete PostgreSQL cutover, validate the real Ubuntu systemd units, and take a
fresh backup before Live. Keep credentials only in the protected service environment.

```text
PAYFAST_ENABLED=True
PAYFAST_CHECKOUT_ENABLED=True
PAYFAST_ITN_ENABLED=True
PAYFAST_API_ENABLED=True
PAYFAST_ENVIRONMENT=live
PAYFAST_MERCHANT_ID=<live merchant id>
PAYFAST_MERCHANT_KEY=<live merchant key>
PAYFAST_PASSPHRASE=<live passphrase>
PAYFAST_API_VERSION=v1
PAYFAST_CALLBACK_BASE_URL=https://www.finy.co.za/
PAYFAST_HTTP_TIMEOUT_SECONDS=10
ALLOWED_HOSTS=127.0.0.1,localhost,finy.co.za,www.finy.co.za,41.61.20.230
CSRF_TRUSTED_ORIGINS=https://finy.co.za,https://www.finy.co.za
RATELIMIT_IP_META_KEY=REMOTE_ADDR
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
SECURE_PROXY_SSL_HEADER_ENABLED=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
SECURE_CONTENT_TYPE_NOSNIFF=True
SECURE_REFERRER_POLICY=same-origin
X_FRAME_OPTIONS=DENY
```

Before switch-over, run the mocked suite plus `manage.py check` and
`manage.py check --deploy` with non-secret production-like values. Confirm all
callbacks through public HTTPS. For emergency rollback, keep master and ITN enabled
but disable checkout and API operations, restart Gunicorn, and verify Billing and ITN
health. This avoids discarding legitimate notifications already in flight.

## Database selection

Local development uses SQLite unless `DATABASE_ENGINE` selects PostgreSQL.

Optional local SQLite configuration:

```text
DATABASE_ENGINE=sqlite
DATABASE_NAME=C:\path\to\finy\db.sqlite3
```

Production must use PostgreSQL:

```text
DATABASE_ENGINE=postgresql
DATABASE_NAME=finy
DATABASE_USER=finy_app
DATABASE_PASSWORD=<set outside source control>
DATABASE_HOST=127.0.0.1
DATABASE_PORT=5432
DATABASE_CONN_MAX_AGE=60
```

`DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, and `DATABASE_HOST` are
mandatory when PostgreSQL is selected. Finy refuses to start when any of them
is blank. Never commit the production environment file.

## Install PostgreSQL

On Ubuntu, install a currently supported PostgreSQL release and its client:

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib postgresql-client
sudo systemctl enable --now postgresql
sudo systemctl status postgresql
```

Django 5.2 supports PostgreSQL 14 and later. Use an Ubuntu/PostgreSQL release
that still receives security updates.

## Create the role and database

Open PostgreSQL's administrative console:

```bash
sudo -u postgres psql
```

Create a dedicated application role and database. Set the password using the
interactive `\password` command so it is not stored in shell history or this
documentation.

```sql
CREATE ROLE finy_app LOGIN;
\password finy_app
CREATE DATABASE finy OWNER finy_app ENCODING 'UTF8';
REVOKE ALL ON DATABASE finy FROM PUBLIC;
\connect finy
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO finy_app;
\quit
```

Allow only the application host to connect. Keep PostgreSQL bound to localhost
when the database and application share a server. For a separate database
server, restrict the firewall and `pg_hba.conf` to the application host and use
TLS.

## Install application dependencies

Finy uses Psycopg 3. Install the pinned requirements in the production virtual
environment:

```bash
/srv/finy/venv/bin/python -m pip install --upgrade pip
/srv/finy/venv/bin/python -m pip install -r /srv/finy/app/requirements.txt
```

The pinned `psycopg[binary]` distribution includes the PostgreSQL client
libraries. PostgreSQL command-line tools are still useful for administration,
backup, and restoration.

## First PostgreSQL migration

Rehearse this procedure on a copy of production data before the maintenance
window. Take both a filesystem copy of the SQLite database and an application
data export. Stop writes before the final export.

With the application still configured for SQLite:

```bash
sudo systemctl stop finy-gunicorn
cp /srv/finy/app/db.sqlite3 /secure-backups/finy-pre-postgresql.sqlite3
/srv/finy/venv/bin/python /srv/finy/app/manage.py dumpdata \
  --natural-foreign --natural-primary \
  --exclude contenttypes --exclude auth.permission \
  --exclude admin.logentry --exclude sessions \
  --indent 2 --output /secure-backups/finy-data.json
```

Configure the production environment with the PostgreSQL variables, then run:

```bash
cd /srv/finy/app
/srv/finy/venv/bin/python manage.py check
/srv/finy/venv/bin/python manage.py migrate --plan
/srv/finy/venv/bin/python manage.py migrate
/srv/finy/venv/bin/python manage.py loaddata /secure-backups/finy-data.json
/srv/finy/venv/bin/python manage.py collectstatic --noinput
/srv/finy/venv/bin/python manage.py check --deploy
```

Compare row counts for users, subscriptions, payments, tasks, folders, spaces,
journey progress, and achievements with the SQLite source. Verify authentication,
workspace loading, Billing history, subscription quotas, and Django Admin before
restarting Gunicorn.

```bash
sudo systemctl restart finy-gunicorn
sudo systemctl status finy-gunicorn
sudo journalctl -u finy-gunicorn -n 100 --no-pager
```

Use the actual Gunicorn unit, project directory, virtual-environment path, and
environment-file location from the production server if they differ from these
examples.

## Backups

Create automated, encrypted, off-host PostgreSQL backups with retention. At a
minimum, take a regular custom-format backup:

```bash
pg_dump --format=custom --file=/secure-backups/finy-$(date +%F).dump finy
```

Do not place database passwords in backup scripts. Use a protected PostgreSQL
password file, service account, or secret manager. Regularly test restoration
into a separate database; an untested backup is not a recovery plan.

## Rollback

Keep the application in maintenance mode until PostgreSQL verification passes.
If migration or verification fails before reopening writes:

1. Stop Gunicorn.
2. Restore the previous SQLite database file from the maintenance-window copy.
3. Restore the prior environment configuration selecting SQLite.
4. Restore the previous application release and dependencies if necessary.
5. Restart Gunicorn and verify authentication and critical application paths.
6. Preserve PostgreSQL logs and the failed database for diagnosis.

Do not switch back to an older SQLite snapshot after users have written data to
PostgreSQL. That would lose those writes. Once production is reopened, recovery
must reconcile or restore PostgreSQL from an appropriate backup instead.

## Subscription lifecycle scheduler

Complete and verify the PostgreSQL cutover before scheduling subscription
lifecycle processing for live subscriptions. Take a current database backup
before the first scheduled production run.

Reviewed systemd templates and installation instructions are provided in
`deploy/README.md`. They use `/srv/finy/app`, `/srv/finy/venv/bin/python`, the
`finy` service account, and `/etc/finy/finy.env` only as proposed conventions.
Match every path and account to the real Gunicorn deployment before installing
the units.

The timer runs `process_subscription_lifecycle` every 15 minutes. The oneshot
service and nonblocking `flock` prevent concurrent processing. Record-level
errors allow other subscriptions to finish but make the command exit nonzero so
systemd and journald expose a partial failure. A lock overlap is a successful
no-op because another valid run is already processing subscriptions.
