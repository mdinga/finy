from django.core.management.base import BaseCommand, CommandError

from subscriptions.lifecycle import process_subscription_lifecycle


class Command(BaseCommand):
    help = "Move overdue Basic subscriptions through grace and downgrade expired grace to Free."

    def handle(self, *args, **options):
        result = process_subscription_lifecycle()
        for error in result.errors:
            self.stderr.write(
                self.style.WARNING(
                    "Subscription lifecycle error: "
                    f"subscription_id={error.subscription_id} "
                    f"error_class={error.error_class} detail={error.detail}"
                )
            )
        summary = (
            "Subscription lifecycle processed: "
            f"checked={result.checked}, "
            f"transitioned={result.transitioned}, "
            f"past_due={result.past_due}, "
            f"downgraded={result.downgraded}, "
            f"unchanged={result.unchanged}, "
            f"errors={len(result.errors)}, "
            f"duration_seconds={result.duration_seconds:.3f}"
        )
        if result.errors:
            self.stdout.write(self.style.WARNING(summary))
            raise CommandError(
                f"Subscription lifecycle completed with {len(result.errors)} error(s)."
            )
        self.stdout.write(self.style.SUCCESS(summary))
