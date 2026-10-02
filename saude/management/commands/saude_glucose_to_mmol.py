"""Converts the stored blood glucose of vital signs from mg/dL to mmol/L (SI).

    python manage.py saude_glucose_to_mmol            # dry run: shows what would change
    python manage.py saude_glucose_to_mmol --apply    # converts, in one transaction

Run it ONCE per environment, right after deploying the version that records
glucose in mmol/L. mmol/L = mg/dL / 18.016, rounded to 2 decimals.

Guard against a second run: a value above 33 can only be mg/dL (33 mmol/L is
already an extreme hyperglycaemia), and a value of 33 or less is almost always
mmol/L. When no stored value is above 33 the command refuses, unless
--force: it looks like the conversion already ran. Soft-deleted rows are
converted too, so a restored record keeps a coherent unit.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from saude.models.dadovital import DadoVital

MG_DL_PER_MMOL_L = Decimal("18.016")
ALREADY_CONVERTED_BELOW = Decimal("33")


def to_mmol(mg_dl):
    return (Decimal(mg_dl) / MG_DL_PER_MMOL_L).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class Command(BaseCommand):
    help = "Converts stored vital-sign blood glucose from mg/dL to mmol/L (run once per environment)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the conversion (default: dry run).")
        parser.add_argument("--force", action="store_true",
                            help="Convert even when every value already looks like mmol/L.")

    def handle(self, *args, **options):
        rows = DadoVital.all_objects.exclude(glicemia=None).only("id", "glicemia")
        values = [row.glicemia for row in rows]

        if not values:
            self.stdout.write("No stored glucose value: nothing to convert.")
            return

        if max(values) <= ALREADY_CONVERTED_BELOW and not options["force"]:
            raise CommandError(
                f"Every one of the {len(values)} stored values is <= {ALREADY_CONVERTED_BELOW}: they look "
                "like mmol/L already (the conversion probably ran). Use --force to convert anyway."
            )

        for row in rows:
            self.stdout.write(f"  {row.id}: {row.glicemia} mg/dL -> {to_mmol(row.glicemia)} mmol/L")

        if not options["apply"]:
            self.stdout.write(self.style.WARNING(f"Dry run: {len(values)} value(s) would be converted. Use --apply."))
            return

        with transaction.atomic():
            for row in DadoVital.all_objects.select_for_update().exclude(glicemia=None):
                DadoVital.all_objects.filter(pk=row.pk).update(glicemia=to_mmol(row.glicemia))

        self.stdout.write(self.style.SUCCESS(f"{len(values)} glucose value(s) converted to mmol/L."))
