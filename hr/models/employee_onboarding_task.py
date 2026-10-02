# hr/models/employee_onboarding_task.py

from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class EmployeeOnboardingTask(BaseModel):
    """A concrete task on a specific EmployeeOnboarding. title/description/
    category/order/is_required are COPIED from the OnboardingTemplateTask
    at start_onboarding() time (see onboarding_service.py) - never a live
    FK to it, so editing a template later never mutates onboardings
    already in progress (pedido secção 31: immutable history, same
    principle Contract/Payslip already follow elsewhere in this app)."""

    onboarding = models.ForeignKey(
        'hr.EmployeeOnboarding',
        on_delete=models.CASCADE,
        related_name='tasks',
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)

    is_done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    done_by = models.ForeignKey(
        'django_resaas.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['onboarding', 'order', 'id']

    class RESAAS:
        label_field = "title"
        search_fields = ["title", "category"]
        crud = True

    def __str__(self):
        return f"{self.onboarding} - {self.title}"
