"""GET sales/dashboard_receivables/: what confirmed sales still owe, aged by
the sale date (0-30, 31-60, 60+ days before as_of). Regression: the age was a
date difference that PostgreSQL returns as an interval, compared with an
integer (500 "operator does not exist: interval <= integer")."""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from sales.models import Payment, Sale
from sales.tests.helpers import make_customer, make_sale
from testutils.tenant import bootstrap_tenant

AS_OF = date(2026, 11, 12)


class ReceivablesDashboardTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("sales-receivables", modules=("sales",),
                                       extra_permissions=("view_dashboard_sales",))
        self.customer = make_customer(self.tenant)

    def _sale(self, days_old, total, estado=Sale.ESTADO_CONFIRMADA):
        sale = make_sale(self.tenant, self.customer)
        # the totals and the state are what the dashboard reads: set directly
        Sale.objects.filter(pk=sale.pk).update(estado=estado, total=Decimal(total),
                                               data=AS_OF - timedelta(days=days_old))
        return sale

    def _get(self):
        response = self.tenant["client"].get("/api/sales/dashboard_receivables/", {"as_of": AS_OF.isoformat()})
        self.assertEqual(response.status_code, 200, response.content)
        return response.data

    def test_balances_are_aged_by_the_sale_date(self):
        self._sale(0, "100")        # today
        self._sale(30, "200")       # last day of 0-30
        self._sale(31, "400")       # first day of 31-60
        self._sale(60, "800")       # last day of 31-60
        self._sale(61, "1600")      # 60+
        data = self._get()
        self.assertEqual(Decimal(str(data["envelhecimento"]["0-30"])), Decimal("300"))
        self.assertEqual(Decimal(str(data["envelhecimento"]["31-60"])), Decimal("1200"))
        self.assertEqual(Decimal(str(data["envelhecimento"]["60+"])), Decimal("1600"))
        self.assertEqual(Decimal(str(data["total_em_divida"])), Decimal("3100"))

    def test_paid_future_and_unconfirmed_sales_owe_nothing(self):
        paid = self._sale(5, "100")
        Payment.objects.create(sale=paid, valor=Decimal("100"), entity=self.tenant["entity"],
                               branch=self.tenant["branch"], created_by=self.tenant["user"],
                               updated_by=self.tenant["user"])
        partly = self._sale(5, "100")
        Payment.objects.create(sale=partly, valor=Decimal("40"), entity=self.tenant["entity"],
                               branch=self.tenant["branch"], created_by=self.tenant["user"],
                               updated_by=self.tenant["user"])
        self._sale(-1, "500")                                   # after as_of
        self._sale(5, "700", estado=Sale.ESTADO_RASCUNHO)
        data = self._get()
        self.assertEqual(Decimal(str(data["total_em_divida"])), Decimal("60"))
        self.assertEqual(Decimal(str(data["envelhecimento"]["0-30"])), Decimal("60"))
