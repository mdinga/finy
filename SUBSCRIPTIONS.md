# Subscription foundation

Finy keeps membership plans and feature entitlements in the `subscriptions` app. The
recurring-payment integration supports explicitly selected PayFast Sandbox or Live checkout for Basic.

## Plans

| Plan | Monthly price | Folders | Spaces | Email capture | AI | Available |
| --- | ---: | ---: | ---: | --- | --- | --- |
| Free | R0 | 5 | 5 | No | No | Yes |
| Basic | R89 | 25 | 15 | Yes | No | Yes |
| Pro | R120 | Unlimited | Unlimited | Yes | Yes | No (coming soon) |

The protected Inbox and protected `waiting_for` space do not count toward plan limits.
Limits represent user-created folders and spaces in addition to those system defaults.
Tasks remain unlimited on every plan. Email capture and AI are entitlements only; the
features are not implemented by this foundation.

Free users have a `Subscription` row with status `free`, no provider, and no billing
period. Paid lifecycle statuses are `active`, `past_due`, `cancelled`, and `expired`.

## Existing and new users

Migration `0002_seed_plans_and_memberships` creates or updates the three plan records
and assigns active Basic membership to existing users without membership data. It does
not overwrite an existing membership. A user creation signal assigns Free membership
to new users, including users created by registration, admin, or `create_user()`.

## Entitlements and limits

All plan policy is exposed through `subscriptions/services.py`. Call
`user_has_feature`, `get_folder_limit`, `get_space_limit`, `can_create_folder`, or
`can_create_space` instead of comparing plan slugs elsewhere. Folder and space API
creation locks the user row and checks the service inside a database transaction.

## PayFast configuration

Authenticated users can initiate recurring Basic checkout in the PayFast sandbox.
Return and cancel pages are informational and ownership-protected; they never change a
subscription. Basic activates only after the ITN signature, source, merchant, amount,
and PayFast server validation all succeed. Attempts, sanitized notifications, and
transactions provide an idempotent audit trail. Pro remains unavailable for purchase.
Provider secrets remain in environment variables and are never stored in source control.

Required manual environment configuration:

```text
PAYFAST_ENABLED=True
PAYFAST_CHECKOUT_ENABLED=True
PAYFAST_ITN_ENABLED=True
PAYFAST_API_ENABLED=True
PAYFAST_ENVIRONMENT=sandbox
PAYFAST_MERCHANT_ID=<sandbox merchant id>
PAYFAST_MERCHANT_KEY=<sandbox merchant key>
PAYFAST_PASSPHRASE=<sandbox passphrase>
PAYFAST_CALLBACK_BASE_URL=<public HTTPS callback base URL>
PAYFAST_HTTP_TIMEOUT_SECONDS=10
PAYFAST_API_VERSION=v1
PAYFAST_TRUSTED_PROXIES=<optional comma-separated proxy IPs>
```

`PAYFAST_ENVIRONMENT` accepts only `sandbox` or `live`. Sandbox uses its
documented checkout and validation endpoints and adds `testing=true` to recurring
API requests. Live uses the `www.payfast.co.za` endpoints and never sends
`testing=true`. Both use `https://api.payfast.co.za` for recurring API operations.
Live callbacks require HTTPS; Sandbox HTTP is allowed only for localhost with
`DEBUG=True`. Callback paths come from named Django routes, not browser input.

For an emergency checkout stop, keep `PAYFAST_ENABLED` and
`PAYFAST_ITN_ENABLED` true while setting checkout and API switches false. Existing
notifications continue to be verified while new checkout and cancellation calls stop.
Secrets must remain outside Git.

Verified renewals extend the existing billing period. Overdue Basic subscriptions
receive a three-day grace period before an automatic downgrade to Free. Sandbox
PayFast subscriptions can be cancelled from Profile: future debits stop after a
confirmed PayFast API response, while Basic access remains until the current period
ends. Cancellation and downgrade never delete productivity data; Free creation limits
apply to any later folders or spaces. Refunds, plan switching, Pro checkout, live mode,
and production configuration remain deliberately excluded.

Authenticated users can review their plan and the ten most recent verified successful
payments at `/subscriptions/billing/`. Billing is the subscription-management surface
for Free upgrades and eligible Basic cancellation. It never displays provider tokens,
provider payment identifiers, notification payloads, signatures, or audit fields.

## Lifecycle operations

`python manage.py process_subscription_lifecycle` reports checked, transitioned,
past-due, downgraded, unchanged, and error counts plus run duration. Individual malformed
subscriptions are identified only by local subscription ID and do not prevent later
records from being processed. Any record error makes the command exit nonzero after the
summary; an entirely successful run exits zero.

The reviewed systemd templates in `deploy/systemd` run this command every 15 minutes.
The oneshot service and a nonblocking runtime lock prevent overlap. A lock overlap logs
`subscription.lifecycle.lock_skipped` and exits successfully without processing because
another valid invocation already owns the work. See `deploy/README.md` for path
substitution, installation, logging, disablement, and rollback instructions.

## Tests

Run the subscription tests:

```powershell
C:\Users\mbasa\Dropbox\finy_code\venv-finy\Scripts\python.exe manage.py test subscriptions ui.tests.RegistrationFlowTests
```

Run the full suite:

```powershell
C:\Users\mbasa\Dropbox\finy_code\venv-finy\Scripts\python.exe manage.py test
```
