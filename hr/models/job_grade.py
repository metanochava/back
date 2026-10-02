from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class JobGrade(BaseModel):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, null=True, blank=True)
    level = models.PositiveIntegerField(
        default=0,
        help_text="Lower first — used to order grades (e.g. Junior=1, Senior=2)."
    )
    description = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['level', 'name']
        unique_together = ('entity', 'name')

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "code"]
        crud = True

    def __str__(self):
        return self.name
