from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class Department(BaseModel):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    manager = models.ForeignKey(
        'hr.Employee',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_departments'
    )

    class Meta:
        ordering = ['name']
        unique_together = ('entity', 'name')

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "code"]
        crud = True

    def __str__(self):
        return self.name