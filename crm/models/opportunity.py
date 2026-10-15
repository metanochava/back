from django.db import models
from django_resaas.saas.core.base.models import BaseModel
from crm.models.lead import Lead
from crm.models.stage import Stage


class Opportunity(BaseModel):
    """A deal in the pipeline. status follows its stage: open, won or lost."""

    STATUS_OPEN = "open"
    STATUS_WON = "won"
    STATUS_LOST = "lost"

    STATUS_CHOICES = (
        (STATUS_OPEN, "Open"),
        (STATUS_WON, "Won"),
        (STATUS_LOST, "Lost"),
    )

    title = models.CharField(max_length=200)
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True, related_name="opportunities")

    # loose reference to sales.Customer (crm does not require sales)
    customer_id = models.UUIDField("Customer", null=True, blank=True)

    stage = models.ForeignKey(Stage, on_delete=models.PROTECT, related_name="opportunities")
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expected_close_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(
        "django_resaas.User", on_delete=models.PROTECT, null=True, blank=True, related_name="crm_opportunities"
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    lost_reason = models.TextField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Opportunity"
        verbose_name_plural = "Opportunities"
        ordering = ["-created_at"]

    class RESAAS:
        label_field = "title"
        search_fields = ["title", "lead__name", "lead__company_name"]
        crud = True
        routes = {"list": "list_opportunity", "view": "view_opportunity"}

    def __str__(self):
        return self.title
