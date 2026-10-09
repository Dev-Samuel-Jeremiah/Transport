from django.core.management.base import BaseCommand

from transit.models import Transit
from transit.services import backfill_transit_weights


class Command(BaseCommand):
    help = (
        "Fill in Transit.cargo_weight_tons (MT) from waybill data for any "
        "transit that is missing it. Safe to re-run."
    )

    def handle(self, *args, **options):
        missing_before = Transit.objects.filter(cargo_weight_tons__isnull=True).count()
        updated = backfill_transit_weights(Transit.objects.all())
        missing_after = Transit.objects.filter(cargo_weight_tons__isnull=True).count()

        self.stdout.write(self.style.SUCCESS(f"Updated {updated} transit(s)."))
        self.stdout.write(
            f"Missing MT before: {missing_before} · still missing: {missing_after} "
            f"(no waybill weight or truck capacity on record)."
        )
