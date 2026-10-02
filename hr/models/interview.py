from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class InterviewMode(models.TextChoices):
    IN_PERSON = "in_person", "In Person"
    VIDEO = "video", "Video"
    PHONE = "phone", "Phone"


class InterviewOutcome(models.TextChoices):
    PENDING = "pending", "Pending"
    PASSED = "passed", "Passed"
    FAILED = "failed", "Failed"


class Interview(BaseModel):
    application = models.ForeignKey(
        'hr.Application',
        on_delete=models.CASCADE,
        related_name='interviews',
    )

    interviewer = models.ForeignKey(
        'hr.Employee',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='interviews_conducted',
    )

    scheduled_at = models.DateTimeField()

    mode = models.CharField(
        max_length=20,
        choices=InterviewMode.choices,
        default=InterviewMode.IN_PERSON,
    )

    notes = models.TextField(blank=True)

    outcome = models.CharField(
        max_length=20,
        choices=InterviewOutcome.choices,
        default=InterviewOutcome.PENDING,
    )

    class Meta:
        ordering = ['-scheduled_at']
        indexes = [
            models.Index(fields=['application']),
        ]

    class RESAAS:
        label_field = "id"
        search_fields = ["application__candidate__full_name", "mode", "outcome"]
        crud = True

    def __str__(self):
        return f"Interview - {self.application} @ {self.scheduled_at}"
