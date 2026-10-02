# hr/models/training_session.py

from django.db import models
from django.core.exceptions import ValidationError

from django_resaas.saas.core.base.models import BaseModel


class TrainingSessionMode(models.TextChoices):
    IN_PERSON = "in_person", "In Person"
    ONLINE = "online", "Online"


class TrainingSessionStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    ONGOING = "ongoing", "Ongoing"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class TrainingSession(BaseModel):
    """A scheduled instance of a Course (pedido secção 35). instructor is
    plain free text rather than an Employee FK - an external trainer is a
    common case this project has no other record for, and forcing every
    instructor to be an Employee would break that."""

    course = models.ForeignKey(
        'hr.Course',
        on_delete=models.CASCADE,
        related_name='sessions',
    )

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    location = models.CharField(max_length=200, blank=True)

    mode = models.CharField(
        max_length=20,
        choices=TrainingSessionMode.choices,
        default=TrainingSessionMode.IN_PERSON,
    )

    instructor = models.CharField(max_length=200, blank=True)

    capacity = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=TrainingSessionStatus.choices,
        default=TrainingSessionStatus.SCHEDULED,
    )

    def clean(self):
        super().clean()

        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({
                "end_date": "The end date cannot be earlier than the start date."
            })

    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['course']),
        ]

    class RESAAS:
        label_field = "id"
        search_fields = ["course__name", "location", "instructor", "status"]
        crud = True

    def __str__(self):
        return f"{self.course} @ {self.start_date}"
