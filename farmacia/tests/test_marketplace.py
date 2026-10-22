"""Marketplace: nearby pharmacies (public), global medicine search (signed in),
prices per pharmacy and availability from real stock."""
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from django_resaas.saas.models.entity_app import EntityApp

from farmacia.models import MedicineCatalogItem, PharmacyOffer
from farmacia.tests.marketplace_helpers import Pharmacy, medicine, next_year, yesterday

PHARMACIES = "/api/farmacia/marketplace/pharmacies/"
MEDICINES = "/api/farmacia/marketplace/medicines/"

# Maputo centre, and two points ~1 km and ~5 km away
ORIGIN = {"lat": "-25.9692", "lng": "32.5732"}


class MarketplaceTestCase(TestCase):

    def setUp(self):
        cache.clear()  # throttle counters
        self.near = Pharmacy("near", lat=-25.9600, lng=32.5732)
        self.far = Pharmacy("far", lat=-25.9250, lng=32.5732, city="Matola")
        self.no_coordinates = Pharmacy("nocoords", city="Beira")
        self.hidden = Pharmacy("hidden", lat=-25.9690, lng=32.5730, published=False)

        self.paracetamol = medicine()
        self.syrup = medicine(name="Paracetamol", strength="120 mg/5 ml", form="Syrup", presentation="Bottle of 100 ml")
        self.amoxicillin = medicine(name="Amoxil", substance="Amoxicillin", brand="Amoxil", strength="500 mg",
                                    form="Capsule", presentation="Box of 21 capsules", prescription_required=True)

        self.near.offer(self.paracetamol, price="85.00", stock=10)
        self.far.offer(self.paracetamol, price="60.00", stock=0)          # sold out
        self.no_coordinates.offer(self.paracetamol, price="70.00", stock=3)
        self.hidden.offer(self.paracetamol, price="10.00", stock=100)     # not published
        self.near.offer(self.syrup, price="150.00", stock=2)
        self.far.offer(self.amoxicillin, price="320.00", lots=[(5, yesterday()), (4, next_year())])

        self.public = APIClient()
        # a signed-in user of another Entity (not a pharmacy)
        self.customer = Pharmacy("customer", modules=()).client

    def search(self, client=None, **params):
        return (client or self.customer).get(MEDICINES, params)


class NearbyPharmaciesTests(MarketplaceTestCase):

    def test_anonymous_sees_published_pharmacies_by_distance_without_invented_values(self):
        response = self.public.get(PHARMACIES, ORIGIN)

        self.assertEqual(response.status_code, 200, response.content)
        rows = response.json()["results"]
        self.assertEqual([row["name"] for row in rows],
                         [self.near.branch.name, self.far.branch.name, self.no_coordinates.branch.name])
        self.assertLess(rows[0]["distance_km"], rows[1]["distance_km"])
        # no coordinates: no distance, listed last
        self.assertIsNone(rows[2]["distance_km"])
        self.assertIsNone(rows[2]["coordinates"])
        self.assertEqual(rows[0]["opening_hours"], "Mon-Fri 8:00-20:00")
        self.assertEqual(rows[0]["currency"], "MZN")

    def test_manual_search_without_location(self):
        response = self.public.get(PHARMACIES, {"city": "matola"})

        rows = response.json()["results"]
        self.assertEqual([row["name"] for row in rows], [self.far.branch.name])
        self.assertIsNone(rows[0]["distance_km"])

    def test_one_field_finds_by_name_address_city_or_country_word_by_word(self):
        def names(q):
            return [row["name"] for row in self.public.get(PHARMACIES, {"q": q}).json()["results"]]

        self.assertEqual(names("matola"), [self.far.branch.name])               # city
        self.assertEqual(names("BEIRA"), [self.no_coordinates.branch.name])     # any case
        self.assertEqual(names(f"{self.far.branch.name} matola"), [self.far.branch.name])  # words in any field
        self.assertEqual(len(names("mozambique")), 3)  # country: not in the formatted address
        self.assertEqual(names("matola beira"), [])                             # every word must match
        self.assertEqual(len(names("")), 3)

    def test_unpublished_or_inactive_module_pharmacies_are_not_listed(self):
        EntityApp.objects.filter(entity=self.near.entity, app__name="farmacia").update(state="Inactive")

        names = {row["name"] for row in self.public.get(PHARMACIES).json()["results"]}

        self.assertNotIn(self.hidden.branch.name, names)
        self.assertNotIn(self.near.branch.name, names)

    def test_malformed_coordinates_are_a_400(self):
        response = self.public.get(PHARMACIES, {"lat": "abc", "lng": "1"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(response.json()), ["error"])

        self.assertEqual(self.public.get(PHARMACIES, {"lat": "95", "lng": "1"}).status_code, 400)
        self.assertEqual(self.public.get(PHARMACIES, {"id": "not-an-id"}).status_code, 400)


class MedicineSearchTests(MarketplaceTestCase):

    def test_search_needs_a_session(self):
        self.assertIn(self.search(self.public, q="paracetamol").status_code, (401, 403))

    def test_search_spans_every_pharmacy_not_only_the_callers_entity(self):
        rows = self.search(q="paracetamol 500").json()["results"]

        pharmacies = {row["pharmacy"]["name"] for row in rows}
        self.assertEqual(pharmacies, {self.near.branch.name, self.far.branch.name, self.no_coordinates.branch.name})
        # a pharmacy searching sees the others too
        rows = self.search(self.near.client, q="paracetamol 500").json()["results"]
        self.assertEqual(len(rows), 3)

    def test_prices_belong_to_each_pharmacy_and_sold_out_is_not_available(self):
        rows = self.search(q="paracetamol tablet").json()["results"]
        by_pharmacy = {row["pharmacy"]["name"]: row for row in rows}

        self.assertEqual(by_pharmacy[self.near.branch.name]["price"], "85.00")
        self.assertEqual(by_pharmacy[self.far.branch.name]["price"], "60.00")
        self.assertTrue(by_pharmacy[self.near.branch.name]["available"])
        self.assertFalse(by_pharmacy[self.far.branch.name]["available"])
        # available first, then by price
        self.assertEqual([row["pharmacy"]["name"] for row in rows],
                         [self.no_coordinates.branch.name, self.near.branch.name, self.far.branch.name])

    def test_presentations_are_different_medicines(self):
        rows = self.search(q="paracetamol").json()["results"]

        medicines = {(row["medicine"]["strength"], row["medicine"]["dosage_form"]) for row in rows}
        self.assertEqual(medicines, {("500 mg", "Tablet"), ("120 mg/5 ml", "Syrup")})
        syrup = self.search(q="paracetamol", dosage_form="syrup").json()["results"]
        self.assertEqual([row["price"] for row in syrup], ["150.00"])

    def test_search_by_active_substance_brand_and_strength(self):
        rows = self.search(q="amoxicillin").json()["results"]
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["medicine"]["prescription_required"])
        self.assertEqual(len(self.search(q="amoxil 500").json()["results"]), 1)
        self.assertEqual(self.search(q="amoxicillin 250").json()["results"], [])

    def test_expired_lots_do_not_count_as_stock(self):
        self.far.listing.show_quantity = True
        self.far.listing.save()

        row = self.search(q="amoxicillin").json()["results"][0]

        self.assertTrue(row["available"])
        self.assertEqual(row["available_quantity"], "4")

    def test_quantity_is_hidden_unless_the_pharmacy_shows_it(self):
        rows = self.search(q="paracetamol 500").json()["results"]
        self.assertTrue(all(row["available_quantity"] is None for row in rows))

    def test_filters_and_sorting(self):
        available = self.search(q="paracetamol 500", available="1").json()["results"]
        self.assertEqual({row["pharmacy"]["name"] for row in available},
                         {self.near.branch.name, self.no_coordinates.branch.name})

        priced = self.search(q="paracetamol 500", min_price="65", max_price="80").json()["results"]
        self.assertEqual([row["price"] for row in priced], ["70.00"])

        nearest = self.search(q="paracetamol 500", sort="distance", **ORIGIN).json()["results"]
        self.assertEqual(nearest[0]["pharmacy"]["name"], self.near.branch.name)
        self.assertIsNotNone(nearest[0]["pharmacy"]["distance_km"])

        self.assertEqual(self.search(q="paracetamol", sort="distance").status_code, 400)
        self.assertEqual(self.search(q="paracetamol", sort="cheapest").status_code, 400)
        self.assertEqual(self.search().status_code, 400)

    def test_results_expose_no_private_data(self):
        row = self.search(q="paracetamol 500").json()["results"][0]

        self.assertEqual(set(row), {
            "offer_id", "medicine", "pharmacy", "price", "currency", "price_source", "available",
            "available_quantity", "online_sale", "checked_at",
        })
        self.assertNotIn("product_id", row)
        self.assertNotIn("custo_unitario", str(row))

    def test_inactive_products_and_offers_are_left_out(self):
        product = self.near.offer(medicine(name="Ibuprofen", substance="Ibuprofen", strength="400 mg"),
                                  price="40", stock=5, ativo=False)
        self.assertEqual(self.search(q="ibuprofen").json()["results"], [])

        PharmacyOffer.objects.filter(product_id=product.id).update(active=False)
        MedicineCatalogItem.objects.filter(name="Paracetamol", strength="500 mg").update(active=False)
        self.assertEqual(self.search(q="paracetamol tablet").json()["results"], [])

    def test_a_too_broad_search_asks_to_refine(self):
        from farmacia import marketplace_service

        original = marketplace_service.MAX_CANDIDATE_OFFERS
        marketplace_service.MAX_CANDIDATE_OFFERS = 2
        try:
            response = self.search(q="paracetamol")
        finally:
            marketplace_service.MAX_CANDIDATE_OFFERS = original

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "search_too_broad")


class MarketplaceManagementTests(MarketplaceTestCase):

    def test_an_offer_can_only_use_a_product_of_its_own_entity(self):
        foreign = self.far.offer(medicine(name="Foreign", substance="X", strength="1 mg"), price="1", stock=1)

        response = self.near.client.post("/api/farmacia/pharmacyoffers/", {
            "catalog_item": str(self.paracetamol.id), "product_id": str(foreign.id),
        }, format="json")

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("product_id", response.json()["error"]["details"])

    def test_the_same_product_cannot_be_offered_twice_by_a_branch(self):
        product = PharmacyOffer.objects.get(branch=self.near.branch, catalog_item=self.paracetamol).product_id

        response = self.near.client.post("/api/farmacia/pharmacyoffers/", {
            "catalog_item": str(self.syrup.id), "product_id": str(product),
        }, format="json")

        self.assertEqual(response.status_code, 400, response.content)

    def test_a_branch_has_one_listing_with_a_valid_currency(self):
        response = self.near.client.post("/api/farmacia/pharmacylistings/", {"currency": "MZN"}, format="json")
        self.assertEqual(response.status_code, 400, response.content)

        other = Pharmacy("listing-new", published=False)
        other.listing.delete()   # soft delete: still blocks a second listing
        deleted = other.client.post("/api/farmacia/pharmacylistings/", {"currency": "MZN"}, format="json")
        self.assertEqual(deleted.status_code, 400, deleted.content)
        other.listing.hard_delete()
        bad = other.client.post("/api/farmacia/pharmacylistings/", {"currency": "metical"}, format="json")
        self.assertEqual(bad.status_code, 400)
        good = other.client.post("/api/farmacia/pharmacylistings/", {"currency": "mzn"}, format="json")
        self.assertEqual(good.status_code, 201, good.content)
        self.assertEqual(good.json()["currency"], "MZN")
        self.assertFalse(good.json()["published"])

    def test_listings_and_offers_are_tenant_scoped(self):
        rows = self.near.client.get("/api/farmacia/pharmacyoffers/").json()["results"]
        self.assertTrue(rows)
        self.assertTrue(all(row["branch"] in (str(self.near.branch.id), {"id": str(self.near.branch.id)}) or
                            str(self.near.branch.id) in str(row["branch"]) for row in rows))

        far_offer = PharmacyOffer.objects.filter(branch=self.far.branch).first()
        self.assertEqual(self.near.client.get(f"/api/farmacia/pharmacyoffers/{far_offer.id}/").status_code, 404)
        self.assertEqual(
            self.near.client.patch(f"/api/farmacia/pharmacylistings/{self.far.listing.id}/",
                                   {"published": False}, format="json").status_code,
            404,
        )
