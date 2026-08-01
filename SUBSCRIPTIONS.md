# Subscription foundation

Finy keeps membership plans and feature entitlements in the `subscriptions` app. The
recurring-payment integration supports explicitly selected PayFast Sandbox or Live checkout for Basic.

## Plans

| Plan | Monthly price | Stored folder value | Stored space value | Available |
| --- | ---: | ---: | ---: | --- |
| Free | R0 | 5 | 5 | Yes |
| Basic | R89 | 25 | 15 | Yes |
| Pro | R120 | Unlimited | Unlimited | No (coming soon) |

The folder, space, and feature fields remain stored for historical account and billing
data, but they do not restrict product access. Every authenticated user can use all
implemented features, including unlimited folders, spaces, tasks, and task files.
Future features default to all authenticated users when implemented unless an
explicit later product decision introduces restrictions.

Free users have a `Subscription` row with status `free`, no provider, and no billing
period. Paid lifecycle statuses are `active`, `past_due`, `cancelled`, and `expired`.

## Existing and new users

Migration `0002_seed_plans_and_memberships` creates or updates the three plan records
and assigns active Basic membership to existing users without membership data. It does
not overwrite an existing membership. A user creation signal assigns Free membership
to new users, including users created by registration, admin, or `create_user()`.

## Feature access

Plan names and subscription states do not control feature access. The compatibility
helpers in `subscriptions/services.py` use an authenticated-by-default policy and
return unlimited folder and space access. Authentication, ownership checks, protected
file delivery, and technical storage limits remain enforced independently.

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

PayFast ITN signatures are validated from the received form body in its original
field order. Blank posted fields are preserved, PHP-style form encoding is used,
the signature field is excluded, and the configured passphrase is appended before
the MD5 digest is calculated. This is distinct from the checkout-form signature
and the recurring API signature.

Verified renewals extend the existing billing period. Overdue Basic subscriptions
receive a three-day grace period before the stored account plan moves to Free. Sandbox
PayFast subscriptions can be cancelled from Profile: future debits stop after a
confirmed PayFast API response, while the Basic subscription remains current until
the period ends. Cancellation and plan changes never delete productivity data or
restrict product features. Refunds, plan switching, Pro checkout, live mode, and
production configuration remain deliberately excluded.

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
