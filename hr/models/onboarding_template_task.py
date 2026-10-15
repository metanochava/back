from django.db import models
from django_resaas.saas.core.base.models import BaseModel
from hr.models.onboarding_task_category import OnboardingTaskCategory


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
