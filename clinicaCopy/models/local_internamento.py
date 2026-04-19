
from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel

class LocalInternamento(TimeModel):

    local = models.TextField(null=True)
    data = models.DateField(null=True, blank=True)
    class Meta:
        permissions = (

        )
    def __str__(self):
        return str(self.local) + str(self.data)