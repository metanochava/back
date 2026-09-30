# hr/models/competency.py

from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class Competency(BaseModel):
    """An Entity's catalog of ratable competencies (e.g. "Communication",
    "Technical Skills"), reused across PerformanceReviews via
    ReviewCompetencyRating - pedido secção 32."""

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['category', 'name']

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "category"]
        crud = True

    def __str__(self):
        return self.name
