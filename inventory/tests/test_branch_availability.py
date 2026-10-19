"""branch_available_quantities() and get_prices(): read-only views of what a
Branch can sell and at what price, for several products at once."""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from django_resaas.saas.models.branch import Branch
from testutils.tenant import bootstrap_tenant

from inventory import services
from inventory.models import PriceList, PriceListItem, Product, StockMovement, Warehouse


def fields(tenant, branch=None):
    return dict(entity=tenant["entity"], branch=branch or tenant["branch"], created_by=tenant["user"],
                updated_by=tenant["user"])


class BranchAvailabilityTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("availability", modules=("inventory",))
        self.ctx = dict(entity_id=self.tenant["entity"].id, branch_id=self.tenant["branch"].id, user=self.tenant["user"])
        self.chair = Product.objects.create(nome="Chair", codigo="CH", preco_base=Decimal("50"), **fields(self.tenant))
        self.milk = Product.objects.create(nome="Milk", codigo="MK", preco_base=Decimal("3"), track_batches=True,
                                           **fields(self.tenant))
        self.repair = Product.objects.create(nome="Repair", codigo="RP", product_type=Product.TYPE_SERVICE,
                                             **fields(self.tenant))
        self.main = Warehouse.objects.create(nome="Main", **fields(self.tenant))
        self.back = Warehouse.objects.create(nome="Back", **fields(self.tenant))
        self.closed = Warehouse.objects.create(nome="Closed", ativo=False, **fields(self.tenant))

        self.move(self.chair, self.main, "6")
        self.move(self.chair, self.back, "4")
        self.move(self.chair, self.closed, "100")
        today = timezone.localdate()
        self.move(self.milk, self.main, "5", lot=("OLD", today - datetime.timedelta(days=1)))
        self.move(self.milk, self.main, "7", lot=("NEW", today + datetime.timedelta(days=30)))

    def move(self, product, warehouse, quantity, lot=None):
        batch = None
        if lot:
            batch = services.get_or_create_batch(product=product, lot_number=lot[0], expiry_date=lot[1], **self.ctx)
        services.apply_movement(product=product, warehouse=warehouse, tipo=StockMovement.TIPO_ENTRADA,
                                quantidade=Decimal(quantity), batch=batch, **self.ctx)

    def available(self, *products, branch_id=None, entity_id=None):
        return services.branch_available_quantities(
            [p.id for p in products], entity_id=entity_id or self.tenant["entity"].id,
            branch_id=branch_id or self.tenant["branch"].id,
        )

    def test_sums_active_warehouses_without_expired_lots_or_reservations(self):
        services.reserve(product=self.chair, warehouse=self.main, quantity=Decimal("2"), source_type="order",
                         source_id="A", **self.ctx)

        result = self.available(self.chair, self.milk, self.repair)

        self.assertEqual(result[self.chair.id], Decimal("8"))   # 6 + 4 - 2, not the closed warehouse
        self.assertEqual(result[self.milk.id], Decimal("7"))    # the expired lot does not count
        self.assertIsNone(result[self.repair.id])               # a service has no stock

    def test_another_branch_or_entity_sees_nothing_of_this_stock(self):
        other_branch = Branch.objects.create(name="Other", entity=self.tenant["entity"])
        self.assertEqual(self.available(self.chair, branch_id=other_branch.id)[self.chair.id], Decimal("0"))

        other = bootstrap_tenant("availability-other", modules=("inventory",))
        self.assertEqual(self.available(self.chair, entity_id=other["entity"].id), {})

    def test_get_prices_uses_a_valid_price_list_else_the_product_price(self):
        price_list = PriceList.objects.create(name="Retail", code="R", **fields(self.tenant))
        PriceListItem.objects.create(price_list=price_list, product=self.chair, price=Decimal("45"),
                                     **fields(self.tenant))

        prices = services.get_prices([self.chair.id, self.milk.id], self.tenant["entity"].id, price_list.id)

        self.assertEqual(prices[self.chair.id]["price"], Decimal("45"))
        self.assertEqual(prices[self.chair.id]["price_list"], str(price_list.id))
        self.assertEqual(prices[self.milk.id], {"price": Decimal("3"), "price_list": None, "ativo": True})
        # the same as get_price(), one product at a time
        single = services.get_price(self.chair.id, self.tenant["entity"].id, price_list.id)
        self.assertEqual(single["price"], prices[self.chair.id]["price"])

        price_list.active = False
        price_list.save()
        prices = services.get_prices([self.chair.id], self.tenant["entity"].id, price_list.id)
        self.assertEqual(prices[self.chair.id]["price"], Decimal("50"))

        other = bootstrap_tenant("prices-other", modules=("inventory",))
        self.assertEqual(services.get_prices([self.chair.id], other["entity"].id), {})
