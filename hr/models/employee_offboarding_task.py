# hr/models/employee_offboarding_task.py

from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class EmployeeOffboardingTask(BaseModel):
    offboarding = models.ForeignKey(
        'hr.EmployeeOffboarding',
        on_delete=models.CASCADE,
        related_name='tasks',
    )

    title = models.CharField(max_length=200)
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
        ordering = ['offboarding', 'order', 'id']

    class RESAAS:
        label_field = "title"
        search_fields = ["title"]
        crud = True

    def __str__(self):
        return f"{self.offboarding} - {self.title}"
