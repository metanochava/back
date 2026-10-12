"""Catalogue: services never hold stock, variants hold it instead of their
template, price lists with validity and quantity breaks, the sale line price
from the customer's price list."""
import datetime
import uuid
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from testutils.tenant import bootstrap_tenant

from inventory import services
from inventory.models import PriceList, PriceListItem, Product, StockMovement, Warehouse


def fields(tenant):
    return dict(entity=tenant["entity"], branch=tenant["branch"], created_by=tenant["user"], updated_by=tenant["user"])


class CatalogueTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("cat", modules=("inventory", "sales"), extra_permissions=("price_product", "preco_sale"))
        self.ctx = dict(entity_id=self.tenant["entity"].id, branch_id=self.tenant["branch"].id, user=self.tenant["user"])
        self.warehouse = Warehouse.objects.create(nome="Main", **fields(self.tenant))
        self.service = Product.objects.create(nome="Installation", product_type=Product.TYPE_SERVICE,
                                              preco_base=Decimal("50"), **fields(self.tenant))
        self.shirt = Product.objects.create(nome="T-shirt", preco_base=Decimal("10"), **fields(self.tenant))
        self.shirt_m = Product.objects.create(nome="T-shirt M", variant_of=self.shirt,
                                              variant_attributes={"Size": "M"}, preco_base=Decimal("12"), **fields(self.tenant))

    def move(self, product, quantity):
        return services.apply_movement(product=product, warehouse=self.warehouse, tipo=StockMovement.TIPO_ENTRADA,
                                       quantidade=Decimal(quantity), **self.ctx)

    def test_service_and_template_hold_no_stock(self):
        with self.assertRaises(ValidationError):
            self.move(self.service, "1")
        with self.assertRaises(ValidationError):
            self.move(self.shirt, "1")
        self.move(self.shirt_m, "5")

    def test_sale_with_a_service_moves_only_the_goods(self):
        self.move(self.shirt_m, "5")
        items = [mock.Mock(product_id=self.service.id, quantidade=Decimal("1"), batch=None),
                 mock.Mock(product_id=self.shirt_m.id, quantidade=Decimal("2"), batch=None)]
        movements = services.commit_sale_movements(sale_id=uuid.uuid4(), warehouse_id=self.warehouse.id, items=items, **self.ctx)
        self.assertEqual([m.product for m in movements], [self.shirt_m])
        availability = services.reserve_stock([{"product_id": self.service.id, "quantidade": Decimal("99")}],
                                              warehouse_id=self.warehouse.id, entity_id=self.tenant["entity"].id)
        self.assertTrue(availability[0]["disponivel"])

    def test_variant_rules_through_the_api(self):
        client = self.tenant["client"]
        response = client.patch(f"/api/inventory/products/{self.shirt.id}/", {"variant_of": str(self.shirt_m.id)}, format="json")
        self.assertEqual(response.status_code, 400)  # a product with variants cannot become one
        other = Product.objects.create(nome="Other", **fields(self.tenant))
        response = client.patch(f"/api/inventory/products/{other.id}/", {"variant_of": str(self.shirt_m.id)}, format="json")
        self.assertEqual(response.status_code, 400)  # a variant cannot have variants
        response = client.patch(f"/api/inventory/products/{self.service.id}/", {"track_batches": True}, format="json")
        self.assertEqual(response.status_code, 400)

        self.move(self.shirt_m, "1")
        response = client.patch(f"/api/inventory/products/{self.shirt_m.id}/", {"product_type": "service"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_price_lists(self):
        today = timezone.localdate()
        wholesale = PriceList.objects.create(name="Wholesale", code="WH", **fields(self.tenant))
        PriceListItem.objects.create(price_list=wholesale, product=self.shirt_m, min_quantity=1, price=Decimal("11"), **fields(self.tenant))
        PriceListItem.objects.create(price_list=wholesale, product=self.shirt_m, min_quantity=10, price=Decimal("9"), **fields(self.tenant))
        expired = PriceList.objects.create(name="Old", code="OLD", valid_to=today - datetime.timedelta(days=1), **fields(self.tenant))
        PriceListItem.objects.create(price_list=expired, product=self.shirt_m, price=Decimal("1"), **fields(self.tenant))

        price = lambda **kw: services.get_price(self.shirt_m.id, self.tenant["entity"].id, **kw)["price"]
        self.assertEqual(price(), Decimal("12"))
        self.assertEqual(price(price_list_id=wholesale.id, quantity=3), Decimal("11"))
        self.assertEqual(price(price_list_id=wholesale.id, quantity=10), Decimal("9"))
        self.assertEqual(price(price_list_id=expired.id), Decimal("12"))
        self.assertEqual(price(price_list_id=wholesale.id, quantity=3, date=today), Decimal("11"))

        other = bootstrap_tenant("cat-other", modules=("inventory",))
        self.assertIsNone(services.get_price(self.shirt_m.id, other["entity"].id))
        self.assertEqual(
            services.get_price(self.shirt_m.id, self.tenant["entity"].id, price_list_id=str(uuid.uuid4()))["price"],
            Decimal("12"),
        )

        response = self.tenant["client"].get(f"/api/inventory/products/{self.shirt_m.id}/price/",
                                             {"price_list": str(wholesale.id), "quantity": "12"})
        self.assertEqual(Decimal(str(response.data["price"])), Decimal("9"))

    def test_sale_line_takes_the_customer_price_list(self):
        from sales.models import Customer, SaleItem
        from sales.tests.helpers import make_customer, make_sale

        wholesale = PriceList.objects.create(name="Wholesale", code="WH", **fields(self.tenant))
        PriceListItem.objects.create(price_list=wholesale, product=self.shirt_m, price=Decimal("11"), **fields(self.tenant))
        client = self.tenant["client"]

        customer = make_customer(self.tenant)
        response = client.patch(f"/api/sales/customers/{customer.id}/", {
            "customer_type": "individual", "person": str(customer.person_id), "price_list_id": str(uuid.uuid4()),
        }, format="json")
        self.assertEqual(response.status_code, 400)
        Customer.objects.filter(id=customer.id).update(price_list_id=wholesale.id)

        sale = make_sale(self.tenant, customer)
        response = client.post("/api/sales/saleitems/", {
            "sale": str(sale.id), "product_id": str(self.shirt_m.id), "quantidade": "2",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(str(response.data["preco_unitario"])), Decimal("11"))

        response = client.post("/api/sales/saleitems/", {
            "sale": str(sale.id), "product_nome": "Gift wrap", "quantidade": "1",
        }, format="json")
        self.assertEqual(response.status_code, 400)  # no product, no price

        response = client.get(f"/api/sales/sales/{sale.id}/preco/", {"product": str(self.shirt_m.id)})
        self.assertEqual(Decimal(str(response.data["data"]["price"])), Decimal("11"))
        self.assertTrue(SaleItem.objects.filter(sale=sale).exists())
