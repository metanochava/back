from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class PayrollPeriod(BaseModel):
    name = models.CharField(max_length=100)

    start_date = models.DateField()
    end_date = models.DateField()

    is_closed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('entity', 'start_date', 'end_date')
        ordering = ['-start_date']

    class RESAAS:
        label_field = "name"
        search_fields = ["name"]
        crud = True

    def __str__(self):
        return self.name