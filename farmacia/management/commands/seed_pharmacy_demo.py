"""Fictitious pharmacies for the online pharmacy (marketplace).

    python manage.py seed_pharmacy_demo --actor-user metano
    python manage.py seed_pharmacy_demo --actor-user metano --pharmacies 5 --entity-type Farmacia
    python manage.py seed_pharmacy_demo --actor-user metano --region ahmedabad --pharmacies 2
    python manage.py seed_pharmacy_demo ... --dry-run

Each pharmacy is a new Entity named "[DEMO] ..."; no real pharmacy, price or
stock is touched. See farmacia/demo_seed_service.py for what is created and
the safety rules. On a database with DEBUG off it refuses to run without
--allow-production: demo pharmacies are not real data and would be published.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from farmacia import demo_seed_service
from farmacia.demo_seed_service import SeedError


class Command(BaseCommand):
    help = "Creates fictitious pharmacies with published listings, prices and stock (online pharmacy demo)."

    def add_arguments(self, parser):
        parser.add_argument("--actor-user", required=True,
                            help="Username or email of an existing user, recorded as author of the demo data.")
        parser.add_argument("--entity-type", default="Farmacia", help="EntityType of the pharmacies (default Farmacia).")
        parser.add_argument("--pharmacies", type=int, default=3,
                            help="Demo pharmacies to have in the region (default 3; mozambique has "
                                 f"{len(demo_seed_service.PHARMACIES)}).")
        parser.add_argument("--region", default="mozambique", choices=list(demo_seed_service.REGIONS),
                            help="Where the demo pharmacies are (default mozambique).")
        parser.add_argument("--dry-run", action="store_true", help="Show what would be created, write nothing.")
        parser.add_argument("--allow-production", action="store_true", help="Required when DEBUG is off.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["allow_production"]:
            raise CommandError("DEBUG is off: this looks like production. Demo pharmacies are not real data; "
                               "pass --allow-production if you really want them here.")
        try:
            report = demo_seed_service.run(
                actor_user=options["actor_user"], entity_type=options["entity_type"],
                pharmacies=options["pharmacies"], dry_run=options["dry_run"], region=options["region"],
            )
        except SeedError as error:
            raise CommandError(str(error))

        style = self.style
        verb = "to create" if options["dry_run"] else "created"
        self.stdout.write(style.MIGRATE_HEADING("DRY RUN - nothing written" if options["dry_run"]
                                                else "Online pharmacy demo data (fictitious)"))
        self.stdout.write(f"Actor: {report.actor}")
        self.stdout.write(f"Catalogue items: {report.catalog_created} {verb}, {report.catalog_reused} reused")
        for pharmacy in report.pharmacies:
            state = "new" if pharmacy["created"] else "existing"
            self.stdout.write(f"  {pharmacy['name']} ({state}): products {pharmacy['products']}, "
                              f"offers {pharmacy['offers']}, units in stock {pharmacy['stock']}")
        self.stdout.write(style.SUCCESS(
            f"Products {verb}: {report.total('products')} | offers {verb}: {report.total('offers')} | "
            f"units {'to receive' if options['dry_run'] else 'received'}: {report.total('stock')}"))
