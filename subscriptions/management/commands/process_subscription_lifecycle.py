from django.core.management.base import BaseCommand

from subscriptions.lifecycle import process_subscription_lifecycle


class Command(BaseCommand):
    help = "Move overdue Basic subscriptions through grace and downgrade expired grace to Free."

    def handle(self, *args, **options):
        result = process_subscription_lifecycle()
        for error in result.errors:
            self.stderr.write(self.style.WARNING(error))
        self.stdout.write(
            self.style.SUCCESS(
                "Subscription lifecycle processed: "
                f"past_due={result.past_due}, "
                f"downgraded={result.downgraded}, "
                f"unchanged={result.unchanged}, "
                f"errors={len(result.errors)}"
            )
        )
