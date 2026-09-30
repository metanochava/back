# hr/models/onboarding_template_task.py

from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class OnboardingTaskCategory(models.TextChoices):
    """Inspired by pedido secção 31's example list, not copied literally -
    trimmed to categories that actually earn their own bucket."""
    DOCUMENTS = "documents", "Documents"
    ACCOUNT = "account", "Account"
    EQUIPMENT = "equipment", "Equipment"
    ORIENTATION = "orientation", "Orientation"
    DEPARTMENT = "department", "Department Induction"
    OTHER = "other", "Other"


class OnboardingTemplateTask(BaseModel):
    template = models.ForeignKey(
        'hr.OnboardingTemplate',
        on_delete=models.CASCADE,
        related_name='tasks',
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    category = models.CharField(
        max_length=20,
        choices=OnboardingTaskCategory.choices,
        default=OnboardingTaskCategory.OTHER,
    )

    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ['template', 'order', 'id']

    class RESAAS:
        label_field = "title"
        search_fields = ["title", "template__name", "category"]
        crud = True

    def __str__(self):
        return f"{self.template} - {self.title}"
