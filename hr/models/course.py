# hr/models/course.py

from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class Course(BaseModel):
    """A catalog entry an Entity can run TrainingSessions against (pedido
    secção 35). provider is a plain free-text field ("Internal" vs an
    external vendor's name) - a choices field would force a fixed vendor
    list this project has no need to enumerate."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)

    duration_hours = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
    )

    provider = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ['name']

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "category", "provider"]
        crud = True

    def __str__(self):
        return self.name
