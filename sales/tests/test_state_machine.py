import uuid
from decimal import Decimal

from django.test import TestCase
from django.core.exceptions import ValidationError

from testutils.tenant import bootstrap_tenant

from sales import services
from sales.models import Sale
from sales.tests.helpers import make_customer, make_sale, make_sale_item


class StateMachineTests(TestCase):
    """
    Máquina de estados explícita: rascunho -> confirmada -> paga ->
    anulada. Cobre transições válidas E inválidas.
    """

    def setUp(self):
        self.tenant = bootstrap_tenant("sm", modules=("sales",))
        self.customer = make_customer(self.tenant)

    def _sale_with_item(self, **sale_kwargs):
        sale = make_sale(self.tenant, self.customer, **sale_kwargs)
        make_sale_item(
            self.tenant, sale,
            product_id=uuid.uuid4(),
            quantidade=Decimal("2"),
            preco_unitario=Decimal("50.00"),
        )
        services.recalculate_totals(sale)
        sale.refresh_from_db()
        return sale

    def test_walk_in_sale_without_customer_completes_full_lifecycle(self):
        """
        Venda de balcão (retalho/supermercado): sem cliente
        identificado. customer=None não pode rebentar em nenhum ponto
        do fluxo (label, confirmar, pagar).
        """
        sale = make_sale(self.tenant, None)
        make_sale_item(
            self.tenant, sale,
            product_id=uuid.uuid4(),
            quantidade=Decimal("1"),
            preco_unitario=Decimal("30.00"),
        )
        services.recalculate_totals(sale)
        sale.refresh_from_db()

        self.assertEqual(sale.cliente_label, "Cliente Balcão")

        services.confirm_sale(sale=sale, user=self.tenant["user"])
        sale.refresh_from_db()
        self.assertEqual(sale.estado, Sale.ESTADO_CONFIRMADA)

        services.add_payment(
            sale=sale, valor=sale.total,
            forma_pagamento="numerario", user=self.tenant["user"]
        )
        sale.refresh_from_db()
        self.assertEqual(sale.estado, Sale.ESTADO_PAGA)

    def test_cannot_confirm_sale_without_items(self):
        sale = make_sale(self.tenant, self.customer)

        with self.assertRaises(ValidationError):
            services.confirm_sale(sale=sale, user=self.tenant["user"])

    def test_confirm_without_warehouse_degrades_explicitly(self):
        sale = self._sale_with_item(warehouse_id=None)

        services.confirm_sale(sale=sale, user=self.tenant["user"])
        sale.refresh_from_db()

        self.assertEqual(sale.estado, Sale.ESTADO_CONFIRMADA)
        self.assertFalse(sale.stock_tracked)

    def test_full_valid_lifecycle(self):
        sale = self._sale_with_item()

        services.confirm_sale(sale=sale, user=self.tenant["user"])
        sale.refresh_from_db()
        self.assertEqual(sale.estado, Sale.ESTADO_CONFIRMADA)

        services.add_payment(
            sale=sale, valor=sale.total,
            forma_pagamento="numerario", user=self.tenant["user"]
        )
        sale.refresh_from_db()
        self.assertEqual(sale.estado, Sale.ESTADO_PAGA)

        services.cancel_sale(sale=sale, user=self.tenant["user"])
        sale.refresh_from_db()
        self.assertEqual(sale.estado, Sale.ESTADO_ANULADA)

    def test_draft_can_be_cancelled_directly(self):
        sale = self._sale_with_item()

        services.cancel_sale(sale=sale, user=self.tenant["user"])
        sale.refresh_from_db()
        self.assertEqual(sale.estado, Sale.ESTADO_ANULADA)

    def test_cannot_skip_from_rascunho_to_paga(self):
        sale = self._sale_with_item()

        with self.assertRaises(ValidationError):
            services._assert_transition(sale, Sale.ESTADO_PAGA)

    def test_cannot_confirm_twice(self):
        sale = self._sale_with_item()
        services.confirm_sale(sale=sale, user=self.tenant["user"])
        sale.refresh_from_db()

        with self.assertRaises(ValidationError):
            services.confirm_sale(sale=sale, user=self.tenant["user"])

    def test_cannot_transition_out_of_anulada(self):
        sale = self._sale_with_item()
        services.cancel_sale(sale=sale, user=self.tenant["user"])
        sale.refresh_from_db()

        with self.assertRaises(ValidationError):
            services.confirm_sale(sale=sale, user=self.tenant["user"])

        with self.assertRaises(ValidationError):
            services.cancel_sale(sale=sale, user=self.tenant["user"])

    def test_payment_rejected_on_draft_sale(self):
        sale = self._sale_with_item()

        with self.assertRaises(ValidationError):
            services.add_payment(
                sale=sale, valor=Decimal("10"),
                forma_pagamento="numerario", user=self.tenant["user"]
            )

    def test_partial_payment_keeps_sale_confirmed(self):
        sale = self._sale_with_item()
        services.confirm_sale(sale=sale, user=self.tenant["user"])
        sale.refresh_from_db()

        services.add_payment(
            sale=sale, valor=sale.total / 2,
            forma_pagamento="numerario", user=self.tenant["user"]
        )
        sale.refresh_from_db()

        self.assertEqual(sale.estado, Sale.ESTADO_CONFIRMADA)
        self.assertGreater(sale.saldo_devedor, Decimal("0"))
