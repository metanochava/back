"""sales.sale.confirming: the validation hook of confirm_sale.

A listener registered with propagate=True may refuse the confirmation; a
listener without propagate must not change the outcome.
"""
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from django_resaas.saas.core.events import EventDispatcher
from testutils.tenant import bootstrap_tenant

from sales import services
from sales.models import Sale
from sales.tests.helpers import make_customer, make_sale, make_sale_item

EVENT = "sales.sale.confirming"


class ConfirmingHookTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("sales-confirming", modules=("sales",))
        self.user = self.tenant["user"]
        self.sale = make_sale(self.tenant, make_customer(self.tenant))
        make_sale_item(self.tenant, self.sale, product_id=uuid.uuid4(),
                       quantidade=Decimal("1"), preco_unitario=Decimal("25.00"))
        services.recalculate_totals(self.sale)
        self._saved = list(EventDispatcher._listeners)

    def tearDown(self):
        EventDispatcher._listeners = self._saved

    def test_without_listeners_confirmation_is_unchanged(self):
        services.confirm_sale(sale=self.sale, user=self.user)

        self.sale.refresh_from_db()
        self.assertEqual(self.sale.estado, Sale.ESTADO_CONFIRMADA)

    def test_propagating_listener_can_refuse_and_nothing_changes(self):
        def refuse(payload):
            raise ValidationError("Blocked by a rule.")

        EventDispatcher.register(EVENT, refuse, propagate=True)

        with self.assertRaises(ValidationError):
            services.confirm_sale(sale=self.sale, user=self.user)

        self.sale.refresh_from_db()
        self.assertNotEqual(self.sale.estado, Sale.ESTADO_CONFIRMADA)

    def test_non_propagating_listener_failure_does_not_stop_confirmation(self):
        def broken(payload):
            raise RuntimeError("listener bug")

        EventDispatcher.register(EVENT, broken)

        services.confirm_sale(sale=self.sale, user=self.user)

        self.sale.refresh_from_db()
        self.assertEqual(self.sale.estado, Sale.ESTADO_CONFIRMADA)

    def test_listener_receives_the_sale_as_instance(self):
        seen = []

        def record(payload):
            seen.append(payload)

        EventDispatcher.register(EVENT, record, propagate=True)

        services.confirm_sale(sale=self.sale, user=self.user)

        self.assertEqual(len(seen), 1)
