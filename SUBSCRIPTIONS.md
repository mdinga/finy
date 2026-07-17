# Subscription foundation

Finy keeps membership plans and feature entitlements in the `subscriptions` app. This
foundation does not perform payment checkout or process PayFast ITN notifications.

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

## Future PayFast integration

After a successful recurring Basic checkout, the PayFast integration can update the
existing `Subscription` with the Basic plan, paid status, billing period, provider
`payfast`, subscription token, and payment ID. Future verified ITN processing can
update those lifecycle fields. Pro remains unavailable for purchase. Provider secrets
must remain in environment variables and must never be stored in source control.

## Tests

Run the subscription tests:

```powershell
C:\Users\mbasa\Dropbox\finy_code\venv-finy\Scripts\python.exe manage.py test subscriptions ui.tests.RegistrationFlowTests
```

Run the full suite:

```powershell
C:\Users\mbasa\Dropbox\finy_code\venv-finy\Scripts\python.exe manage.py test
```
