from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class FiscalPeriod(BaseModel):
    """A period entries are dated in. When an Entity has periods, an entry can
    only be posted on a date inside an OPEN one; closing a period freezes it."""

    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = (
        (STATUS_OPEN, "Open"),
        (STATUS_CLOSED, "Closed"),
    )

    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)

    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        "django_resaas.User", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        verbose_name = "Fiscal period"
        verbose_name_plural = "Fiscal periods"
        ordering = ["-start_date"]

    class RESAAS:

        label_field = "name"

        search_fields = ["name"]

        crud = True

        routes = {
            "list": "list_fiscalperiod",
        }

    def __str__(self):
        return self.name
