# hr/models/performance_cycle.py

from django.db import models
from django.core.exceptions import ValidationError

from django_resaas.saas.core.base.models import BaseModel


class PerformanceCycleStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    CLOSED = "closed", "Closed"


class PerformanceCycle(BaseModel):
    """An evaluation period (e.g. "2026 H1") an Entity's Goals/Reviews are
    scoped to (pedido secção 32/34)."""

    name = models.CharField(max_length=150)

    start_date = models.DateField()
    end_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=PerformanceCycleStatus.choices,
        default=PerformanceCycleStatus.DRAFT,
    )

    def clean(self):
        super().clean()

        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({
                "end_date": "The end date cannot be earlier than the start date."
            })

    class Meta:
        ordering = ['-start_date']

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "status"]
        crud = True

    def __str__(self):
        return self.name
