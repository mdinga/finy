# Finy Project Instructions

## Project overview

Finy is a GTD inspired productivity application built with Django 5.2 and Django REST Framework.

The project includes:

1. Task management.
2. Folders and spaces.
3. Journeys, missions and achievements.
4. Subscription plans and entitlement controls.
5. A future PayFast recurring payment integration.
6. Future email capture and analytics features.

## Repository rules

1. Inspect the relevant code before making changes.
2. Follow the existing architecture and coding style.
3. Avoid unnecessary refactoring.
4. Preserve existing functionality unless the task explicitly requires a change.
5. Do not modify unrelated files.
6. Do not deploy unless explicitly instructed.
7. Do not apply production migrations unless explicitly instructed.
8. Do not modify production data.
9. Do not expose, print or commit secrets.
10. Do not commit changes unless explicitly instructed.

## Testing

Before implementing a change:

1. Run the relevant existing tests where practical.
2. Record the baseline result.

After implementing a change:

1. Run focused tests for the changed feature.
2. Run the full Django test suite.
3. Run Django system checks.
4. Run makemigrations with the check option to confirm migration consistency.
5. Report all test results clearly.

Use the project virtual environment when running commands.

Development Python command:

C:\Users\mbasa\Dropbox\finy_code\venv-finy\Scripts\python.exe

Common commands:

C:\Users\mbasa\Dropbox\finy_code\venv-finy\Scripts\python.exe manage.py test

C:\Users\mbasa\Dropbox\finy_code\venv-finy\Scripts\python.exe manage.py check

C:\Users\mbasa\Dropbox\finy_code\venv-finy\Scripts\python.exe manage.py makemigrations --check --dry-run

## Subscription rules

All subscription and entitlement rules must remain centralized in subscriptions/services.py.

Do not scatter direct plan checks such as:

user.subscription.plan.slug == "pro"

Use the subscription service helpers instead.

Current plans:

### Free

Price: R0 per month.

Includes:

1. Unlimited tasks.
2. Five user created folders.
3. Five user created spaces.
4. Journeys.
5. Mission videos.
6. Achievements.
7. Calendar and review features.

### Basic

Price: R89 per month.

Includes:

1. Everything in Free.
2. Twenty five user created folders.
3. Fifteen user created spaces.
4. Email capture when launched.
5. Selected premium features.

### Pro

Price: R120 per month.

Pro currently exists in the data model but is unavailable for purchase.

Includes:

1. Unlimited folders.
2. Unlimited spaces.
3. Email capture.
4. AI features.
5. Advanced analytics.
6. Future premium features.

## Folder and space rules

1. The protected Inbox folder does not count toward folder quotas.
2. Protected system spaces do not count toward space quotas.
3. The waiting_for space must be marked as a system space.
4. Never identify system items only by their name.
5. Use the relevant model fields such as is_inbox and is_system.
6. Folder and space limits must be enforced at the backend API boundary.
7. Successful folder and space creation must continue updating Journey progress.
8. Rejected quota requests must not update Journey progress.
9. Tasks remain unlimited on all plans.

## Payments

PayFast will be used for recurring subscription payments.

Payment work must:

1. Use sandbox credentials during development.
2. Store all credentials in environment variables.
3. Never place Merchant ID, Merchant Key or passphrase directly in source code.
4. Verify PayFast ITN notifications before activating subscriptions.
5. Never activate a subscription solely because the user returned from the PayFast payment page.
6. Treat ITN processing as idempotent.
7. Record payment provider references safely.
8. Keep checkout, signature generation and ITN verification in a dedicated service layer.
9. Keep Pro unavailable until explicitly enabled.
10. Avoid changing live PayFast settings during development.

## Migrations

1. Review generated migrations before applying them.
2. Data migrations must preserve existing users and existing data.
3. Existing subscriptions must not be overwritten unnecessarily.
4. Do not apply migrations automatically unless explicitly instructed.
5. Never apply production migrations without explicit approval.

## Git

1. Review git status before starting.
2. Preserve pre existing uncommitted changes.
3. Never include unrelated changes in a commit.
4. Show a diff summary before committing.
5. Use clear commit messages.
6. Do not push or deploy unless explicitly instructed.

## Completion report

At the end of each task report:

1. What changed.
2. Files changed.
3. Migrations created.
4. Focused test results.
5. Full test results.
6. System check results.
7. Manual checks still required.
8. Work deliberately excluded from the task.
