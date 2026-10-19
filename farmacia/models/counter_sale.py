from django.conf import settings
from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class CounterSale(BaseModel):
    """
    A sale made at the pharmacy counter - walk-in, or the collection of an
    online order. The commercial record is the confirmed and paid sales.Sale
    (sale_id); this row keeps what only the pharmacy knows: which offers were
    sold and who verified a PAPER prescription. "Verified by the pharmacist"
    is a person's statement, never a validation by the system.
    """

    sale_id = models.UUIDField(verbose_name="Sale")
    online_order = models.OneToOneField("farmacia.OnlineOrder", verbose_name="Online order",
                                        on_delete=models.PROTECT, null=True, blank=True,
                                        related_name="counter_sale")
    total = models.DecimalField(verbose_name="Total", max_digits=14, decimal_places=2)
    payment_method = models.CharField(verbose_name="Payment method", max_length=20)
    payment_reference = models.CharField(verbose_name="Payment reference", max_length=100, blank=True, default="")
    prescription_required = models.BooleanField(verbose_name="Prescription required", default=False)
    prescription_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Prescription verified by", on_delete=models.PROTECT,
        null=True, blank=True, related_name="+",
    )
    # number / prescriber written on the paper prescription, as read by the pharmacist
    prescription_reference = models.CharField(verbose_name="Prescription reference", max_length=120,
                                              blank=True, default="")
    # one sale per request: a retried request returns the same sale
    idempotency_key = models.CharField(verbose_name="Idempotency key", max_length=64)

    class Meta:
        verbose_name = "Counter sale"
        verbose_name_plural = "Counter sales"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "idempotency_key"], name="unique_counter_sale_per_request"),
        ]

    class RESAAS:
        label_field = "sale_id"
        search_fields = ["prescription_reference", "payment_reference"]
        crud = False
        routes = {
            "list": "list_countersale",
            "view": "view_countersale",
        }

    def __str__(self):
        return f"{self.sale_id} ({self.total})"
