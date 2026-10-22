"""manage.py seed_pharmacy_demo (farmacia/demo_seed_service.py)."""
from decimal import Decimal
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from django_resaas.saas.models.app import App
from django_resaas.saas.models.entity import Entity
from django_resaas.saas.models.entity_app import EntityApp
from django_resaas.saas.models.entity_type import EntityType
from inventory.models import Product, StockMovement

from farmacia import demo_seed_service
from farmacia.demo_seed_service import DEMO_PREFIX, MEDICINES, SeedError
from farmacia.models import MedicineCatalogItem, PharmacyListing, PharmacyOffer
from farmacia.tests.marketplace_helpers import Pharmacy, medicine


def counts():
    return (Entity.objects.count(), Product.objects.count(), StockMovement.objects.count(),
            PharmacyOffer.all_objects.count(), PharmacyListing.all_objects.count(),
            MedicineCatalogItem.objects.count())


class PharmacyDemoSeedTests(TestCase):

    def setUp(self):
        self.real = Pharmacy("real-pharmacy")
        self.user = self.real.user
        EntityType.objects.create(name="Farmacia")
        for name in ("farmacia", "inventory", "sales"):
            App.objects.get_or_create(name=name)

    def run_seed(self, **kwargs):
        options = {"actor_user": self.user.username, "pharmacies": 3}
        options.update(kwargs)
        return demo_seed_service.run(**options)

    def test_creates_marked_pharmacies_with_published_listing_prices_and_stock(self):
        report = self.run_seed()

        demo = Entity.objects.filter(name__startswith=DEMO_PREFIX)
        self.assertEqual(demo.count(), 3)
        for entity in demo:
            self.assertEqual(set(EntityApp.objects.filter(entity=entity, state="Active")
                                 .values_list("app__name", flat=True)), {"farmacia", "inventory", "sales"})
            self.assertTrue(PharmacyListing.objects.get(entity=entity).published)
            self.assertEqual(PharmacyOffer.objects.filter(entity=entity).count(), len(MEDICINES))
            self.assertTrue(all(p.nome.endswith("(demo)") for p in Product.objects.filter(entity=entity)))
        self.assertEqual(report.total("offers"), 3 * len(MEDICINES))
        self.assertEqual(report.catalog_created, len(MEDICINES))
        received = sum(StockMovement.objects.filter(entity__in=demo).values_list("quantidade", flat=True))
        self.assertEqual(Decimal(report.total("stock")), received)

    def test_demo_pharmacies_appear_in_the_marketplace_search(self):
        self.run_seed()

        response = self.real.client.get("/api/farmacia/marketplace/medicines/", {"q": "Paracetamol"})

        self.assertEqual(response.status_code, 200)
        names = {row["pharmacy"]["organisation"] for row in response.json()["results"]}
        self.assertEqual(len([n for n in names if n.startswith(DEMO_PREFIX)]), 3)
        prices = {row["price"] for row in response.json()["results"]}
        self.assertGreater(len(prices), 1)   # each pharmacy has its own price

    def test_running_again_creates_nothing_new(self):
        self.run_seed()
        before = counts()

        report = self.run_seed()

        self.assertEqual(counts(), before)
        self.assertEqual((report.total("products"), report.total("offers"), report.total("stock")), (0, 0, 0))
        self.assertEqual(report.catalog_reused, len(MEDICINES))

    def test_more_pharmacies_later_only_adds_the_new_ones(self):
        self.run_seed(pharmacies=2)
        report = self.run_seed(pharmacies=4)

        self.assertEqual([p["created"] for p in report.pharmacies], [False, False, True, True])
        self.assertEqual(Entity.objects.filter(name__startswith=DEMO_PREFIX).count(), 4)

    def test_dry_run_writes_nothing(self):
        before = counts()

        report = self.run_seed(dry_run=True)

        self.assertEqual(counts(), before)
        self.assertEqual(report.total("offers"), 3 * len(MEDICINES))

    def test_real_pharmacies_and_catalogue_items_are_not_changed(self):
        item = medicine(name="Paracetamol", substance="Paracetamol", strength="500 mg", form="Tablet",
                        presentation="Box of 20 tablets", code="REAL-1", prescription_required=True)
        product = self.real.offer(item, price="99", stock=7)
        movements = StockMovement.objects.filter(entity=self.real.entity).count()

        self.run_seed()

        item.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual((item.code, item.prescription_required), ("REAL-1", True))   # reused, untouched
        self.assertEqual(product.preco_base, Decimal("99"))
        self.assertEqual(StockMovement.objects.filter(entity=self.real.entity).count(), movements)
        self.assertEqual(PharmacyOffer.objects.filter(entity=self.real.entity).count(), 1)
        self.assertEqual(PharmacyOffer.objects.filter(catalog_item=item).count(), 4)

    def test_region_places_the_pharmacies_with_its_country_and_currency(self):
        report = self.run_seed(region="ahmedabad", pharmacies=2)

        demo = Entity.objects.filter(name__startswith=DEMO_PREFIX)
        self.assertEqual(demo.count(), 2)
        self.assertEqual(report.total("offers"), 2 * len(MEDICINES))
        for listing in PharmacyListing.objects.filter(entity__in=demo):
            self.assertEqual(listing.currency, "INR")
            address = listing.branch.addresses.get()
            self.assertEqual((address.country, address.locality), ("India", "Ahmedabad"))
        with self.assertRaises(SeedError):
            self.run_seed(region="ahmedabad", pharmacies=3)
        with self.assertRaises(SeedError):
            self.run_seed(region="nowhere")

    def test_inputs_are_explicit(self):
        with self.assertRaises(SeedError):
            self.run_seed(actor_user="nobody")
        with self.assertRaises(SeedError):
            self.run_seed(entity_type="Nope")
        with self.assertRaises(SeedError):
            self.run_seed(pharmacies=0)
        self.assertFalse(Entity.objects.filter(name__startswith=DEMO_PREFIX).exists())

    @override_settings(DEBUG=False)
    def test_command_refuses_production_without_the_flag(self):
        with self.assertRaises(CommandError):
            call_command("seed_pharmacy_demo", actor_user=self.user.username, stdout=StringIO())
        self.assertFalse(Entity.objects.filter(name__startswith=DEMO_PREFIX).exists())

    @override_settings(DEBUG=True)
    def test_command_reports_the_counts(self):
        out = StringIO()
        call_command("seed_pharmacy_demo", actor_user=self.user.username, pharmacies=2, stdout=out)

        self.assertIn(f"offers created: {2 * len(MEDICINES)}", out.getvalue())
