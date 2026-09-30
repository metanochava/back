from django.core.exceptions import ValidationError
from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class JobOpeningStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    OPEN = "open", "Open"
    ON_HOLD = "on_hold", "On Hold"
    CLOSED = "closed", "Closed"
    CANCELLED = "cancelled", "Cancelled"


class JobOpening(BaseModel):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    department = models.ForeignKey(
        'hr.Department',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='job_openings',
    )

    position = models.ForeignKey(
        'hr.JobPosition',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='job_openings',
    )

    job_grade = models.ForeignKey(
        'hr.JobGrade',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='job_openings',
    )

    openings_count = models.PositiveIntegerField(default=1)

    status = models.CharField(
        max_length=20,
        choices=JobOpeningStatus.choices,
        default=JobOpeningStatus.DRAFT,
    )

    opened_at = models.DateField(null=True, blank=True)
    closed_at = models.DateField(null=True, blank=True)

    def clean(self):
        super().clean()

        if (
            self.opened_at
            and self.closed_at
            and self.closed_at < self.opened_at
        ):
            raise ValidationError({
                "closed_at": "closed_at cannot be earlier than opened_at."
            })

    class Meta:
        ordering = ['-created_at']

    class RESAAS:
        label_field = "title"
        search_fields = ["title", "status"]
        crud = True

    def __str__(self):
        return self.title
