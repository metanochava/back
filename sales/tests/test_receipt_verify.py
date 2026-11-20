"""The printed receipt can be verified (QR code -> public page) and found again
by its number (barcode -> the sales search)."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from django_resaas.saas.core.printing.verify import make_token
from sales.models import Sale
from testutils.tenant import bootstrap_tenant


def _sale(tenant, estado):
    return Sale.objects.create(entity=tenant["entity"], branch=tenant["branch"], created_by=tenant["user"],
                               updated_by=tenant["user"], state="Active", estado=estado, total=Decimal("80.00"))


class ReceiptVerifyTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("receipt-verify", modules=("sales",))

    def verify(self, sale):
        return APIClient().get(f"/api/printing/verify/{make_token('sales.receipt', sale)}/")

    def test_a_paid_receipt_is_authentic_and_says_paid(self):
        response = self.verify(_sale(self.tenant, Sale.ESTADO_PAGA))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["voided"])
        values = {f["label"]: f["value"] for f in response.data["fields"]}
        self.assertEqual(values["Total"], "80.00")

    def test_a_voided_sale_says_so(self):
        response = self.verify(_sale(self.tenant, Sale.ESTADO_ANULADA))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["voided"])

    def test_an_unpaid_sale_has_no_receipt_to_verify(self):
        self.assertEqual(self.verify(_sale(self.tenant, Sale.ESTADO_RASCUNHO)).status_code, 404)

    def test_the_receipt_number_finds_the_sale_in_this_tenant_only(self):
        sale = _sale(self.tenant, Sale.ESTADO_PAGA)
        number = str(sale.id)[:8].upper()

        found = self.tenant["client"].get("/api/sales/sales/", {"search": number})
        self.assertEqual([row["id"] for row in found.data["results"]], [str(sale.id)])

        other = bootstrap_tenant("receipt-verify-b", modules=("sales",))
        self.assertEqual(other["client"].get("/api/sales/sales/", {"search": number}).data["results"], [])
