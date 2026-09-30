# hr/models/onboarding_template.py

from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class OnboardingTemplate(BaseModel):
    """A reusable checklist definition for an Entity (pedido secção 31) -
    optionally scoped to a Department/Position so a role can have its own
    onboarding, or left generic. EmployeeOnboarding (below) copies this
    template's tasks at start time rather than referencing it live."""

    name = models.CharField(max_length=150)

    department = models.ForeignKey(
        'hr.Department',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='onboarding_templates',
    )

    position = models.ForeignKey(
        'hr.JobPosition',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='onboarding_templates',
    )

    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    class RESAAS:
        label_field = "name"
        search_fields = ["name"]
        crud = True

    def __str__(self):
        return self.name
