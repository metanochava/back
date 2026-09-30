from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class Holiday(BaseModel):
    name = models.CharField(max_length=150)
    date = models.DateField()

    # BaseModel.branch (required on every row - see core/base/models.py)
    # records which Branch the row was created under, but a holiday can
    # still apply to every Branch of the Entity: is_entity_wide=True (the
    # default) means "ignore this row's own branch and match any branch
    # of the entity" (pedido secção 27: holidays por Entity/Branch).
    # False scopes it to just BaseModel.branch.
    is_entity_wide = models.BooleanField(default=True)

    # Annual holidays (Christmas, national day, ...) repeat on the same
    # month/day every year without a new row per year.
    is_recurring = models.BooleanField(default=True)

    class Meta:
        ordering = ['date']
        unique_together = ('entity', 'branch', 'date', 'name')

    class RESAAS:
        label_field = "name"
        search_fields = ["name"]
        crud = True

    def __str__(self):
        return f"{self.name} ({self.date})"
