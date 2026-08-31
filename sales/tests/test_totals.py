import uuid
from decimal import Decimal

from django.test import TestCase

from testutils.tenant import bootstrap_tenant

from sales import services
from sales.models import Sale
from sales.tests.helpers import make_customer, make_sale, make_sale_item


class TotalsTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("totals", modules=("sales",))
        self.customer = make_customer(self.tenant)
        self.sale = make_sale(self.tenant, self.customer)

    def test_totals_computed_from_items(self):
        make_sale_item(
            self.tenant, self.sale, product_id=uuid.uuid4(),
            quantidade=Decimal("3"), preco_unitario=Decimal("20.00"),
            desconto_valor=Decimal("5.00"),
        )
        make_sale_item(
            self.tenant, self.sale, product_id=uuid.uuid4(),
            quantidade=Decimal("1"), preco_unitario=Decimal("100.00"),
        )

        services.recalculate_totals(self.sale)
        self.sale.refresh_from_db()

        # (3*20) + (1*100) = 160 subtotal ; desconto 5 ; total 155
        self.assertEqual(self.sale.subtotal, Decimal("160.00"))
        self.assertEqual(self.sale.desconto_total, Decimal("5.00"))
        self.assertEqual(self.sale.total, Decimal("155.00"))

    def test_totals_recalculated_when_item_removed(self):
        item = make_sale_item(
            self.tenant, self.sale, product_id=uuid.uuid4(),
            quantidade=Decimal("2"), preco_unitario=Decimal("30.00"),
        )
        services.recalculate_totals(self.sale)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.total, Decimal("60.00"))

        item.delete(user=self.tenant["user"])
        services.recalculate_totals(self.sale)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.total, Decimal("0.00"))

    def test_client_supplied_total_is_ignored_by_serializer(self):
        from sales.serializers.sale import SaleSerializer

        make_sale_item(
            self.tenant, self.sale, product_id=uuid.uuid4(),
            quantidade=Decimal("1"), preco_unitario=Decimal("10.00"),
        )
        services.recalculate_totals(self.sale)
        real_total = self.sale.total

        serializer = SaleSerializer(
            self.sale,
            data={
                "customer": str(self.customer.id),
                "total": "999999.00",
                "estado": Sale.ESTADO_PAGA,
            },
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        self.sale.refresh_from_db()
        self.assertEqual(self.sale.total, real_total)
        self.assertEqual(self.sale.estado, Sale.ESTADO_RASCUNHO)
