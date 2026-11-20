from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class DiningArea(BaseModel):
    """A part of a branch where the tables are: the room, the terrace, the
    bar counter, the VIP area."""

    name = models.CharField(max_length=60)
    order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Dining area"
        verbose_name_plural = "Dining areas"
        ordering = ["order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "name"], name="unique_dining_area_name_per_branch"),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name"]
        crud = True
        routes = {"list": "list_diningarea"}

    def __str__(self):
        return self.name
