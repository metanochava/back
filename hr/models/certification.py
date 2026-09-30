# hr/models/certification.py

from django.db import models

from django_resaas.saas.core.base.models import BaseModel


def certificate_file_path(instance, file_name):
    return f"hr/certifications/{instance.employee_id}/{file_name}"


class Certification(BaseModel):
    """A certificate an Employee holds - either issued off an internal
    EmployeeTraining (training set) or standalone, an external
    certification the employee already had before joining (training left
    null). file is a plain FileField, not the generic Document model
    (saas/models/document.py) - same reasoning as Candidate.resume
    (hr/models/candidate.py, Fase 4): Document requires a `numero` unique
    per DocumentType, a worse fit for a training certificate scan."""

    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='certifications',
    )

    training = models.ForeignKey(
        'hr.EmployeeTraining',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='certifications',
    )

    name = models.CharField(max_length=200)
    issued_by = models.CharField(max_length=200, blank=True)
    issued_at = models.DateField()
    expires_at = models.DateField(null=True, blank=True)

    file = models.FileField(upload_to=certificate_file_path, null=True, blank=True)

    class Meta:
        ordering = ['-issued_at']
        indexes = [
            models.Index(fields=['employee']),
            models.Index(fields=['expires_at']),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "issued_by", "employee__person__full_name"]
        crud = True

    def __str__(self):
        return f"{self.name} - {self.employee}"
