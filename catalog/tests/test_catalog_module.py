"""The catalog as its own horizontal module: goods and services of an Entity
with only the catalog active (no inventory), tenant isolation, the module
gate, the public services other modules use, and the move out of inventory
(same rows, content type and permissions in catalog)."""
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from catalog import services
from catalog.models import PriceList, PriceListItem, Product
from testutils.tenant import bootstrap_tenant

URL = "/api/catalog/products/"


def _audit(tenant):
    return {"entity": tenant["entity"], "branch": tenant["branch"],
            "created_by": tenant["user"], "updated_by": tenant["user"], "state": "Active"}


class CatalogWithoutInventoryTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("catalog-only", modules=("catalog",))
        self.client_ = self.tenant["client"]

    def test_goods_and_services_are_kept_without_inventory(self):
        service = self.client_.post(URL, {"nome": "Consultation", "codigo": "SRV-1", "product_type": "service",
                                          "preco_base": "1500.00"}, format="json")
        self.assertEqual(service.status_code, 201, service.content)
        goods = self.client_.post(URL, {"nome": "Gloves", "codigo": "GDS-1", "preco_base": "50.00"}, format="json")
        self.assertEqual(goods.status_code, 201, goods.content)

        names = {row["nome"] for row in self.client_.get(URL, {"page_size": 50}).data["results"]}
        self.assertEqual(names, {"Consultation", "Gloves"})

        price = self.client_.get(f"{URL}{service.data['id']}/price/").data
        self.assertEqual(Decimal(str(price["price"])), Decimal("1500.00"))

    def test_a_service_never_holds_stock(self):
        service = Product.objects.create(nome="Exam", product_type=Product.TYPE_SERVICE, **_audit(self.tenant))
        goods = Product.objects.create(nome="Reagent", **_audit(self.tenant))
        self.assertFalse(services.is_stockable(service))
        self.assertTrue(services.is_stockable(goods))

    def test_another_entity_sees_none_of_it(self):
        mine = Product.objects.create(nome="Mine", **_audit(self.tenant))
        other = bootstrap_tenant("catalog-other", modules=("catalog",))

        self.assertEqual(other["client"].get(URL).data["results"], [])
        self.assertEqual(other["client"].get(f"{URL}{mine.id}/").status_code, 404)
        self.assertIsNone(services.get_product_snapshot(mine.id, entity_id=other["entity"].id))
        self.assertEqual(services.get_product_snapshot(mine.id, entity_id=self.tenant["entity"].id)["nome"], "Mine")

    def test_the_module_must_be_active(self):
        # an Entity without catalog (nor any of its consumer modules)
        inactive = bootstrap_tenant("catalog-inactive", modules=("saude",))
        self.assertEqual(inactive["client"].get(URL).status_code, 403)

    def test_its_consumer_modules_bring_the_catalog(self):
        from django_resaas.saas.models.entity_app import EntityApp

        with_sales = bootstrap_tenant("catalog-consumer", modules=("sales",))
        self.assertTrue(EntityApp.objects.filter(entity=with_sales["entity"], app__name="catalog",
                                                 state="Active").exists())

    def test_price_lists_are_the_catalogs(self):
        goods = Product.objects.create(nome="Box", preco_base=Decimal("10"), **_audit(self.tenant))
        price_list = PriceList.objects.create(name="Wholesale", code="W", **_audit(self.tenant))
        PriceListItem.objects.create(price_list=price_list, product=goods, min_quantity=Decimal("10"),
                                     price=Decimal("8"), **_audit(self.tenant))

        self.assertEqual(services.get_price(goods.id, self.tenant["entity"].id, price_list_id=price_list.id,
                                            quantity=12)["price"], Decimal("8"))
        self.assertEqual(services.get_price(goods.id, self.tenant["entity"].id, price_list_id=price_list.id,
                                            quantity=1)["price"], Decimal("10"))


class CatalogMoveTests(TestCase):

    def test_the_catalogue_kept_its_tables_and_belongs_to_catalog(self):
        self.assertEqual(Product._meta.db_table, "inventory_product")
        self.assertEqual(ContentType.objects.get_for_model(Product).app_label, "catalog")

    def test_inventory_keeps_working_through_its_compatibility_names(self):
        from inventory import services as inventory_services
        from inventory.models import Product as InventoryProduct

        self.assertIs(InventoryProduct, Product)
        tenant = bootstrap_tenant("catalog-compat", modules=("inventory",))
        goods = Product.objects.create(nome="Old", **_audit(tenant))
        self.assertEqual(inventory_services.get_product_snapshot(goods.id, entity_id=tenant["entity"].id)["nome"], "Old")
        # the old route answers while the inventory module is active
        self.assertEqual(tenant["client"].get(f"/api/inventory/products/{goods.id}/").status_code, 200)
