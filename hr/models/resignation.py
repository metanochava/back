# hr/models/resignation.py

from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class ResignationStatus(models.TextChoices):
    SUBMITTED = "submitted", "Submitted"
    ACCEPTED = "accepted", "Accepted"
    WITHDRAWN = "withdrawn", "Withdrawn"


ALLOWED_TRANSITIONS = {
    ResignationStatus.SUBMITTED: {
        ResignationStatus.ACCEPTED,
        ResignationStatus.WITHDRAWN,
    },
    ResignationStatus.ACCEPTED: set(),
    ResignationStatus.WITHDRAWN: set(),
}


class Resignation(BaseModel):
    """Submitting a resignation is plain CRUD create (same pattern as
    LeaveRequest starting DRAFT) - only the ACCEPTED/WITHDRAWN transitions
    are actions, since ACCEPTED is what actually changes
    Employee.employment_status (see lifecycle_service.accept_resignation)."""

    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='resignations',
    )

    resignation_date = models.DateField()
    last_working_date = models.DateField()
    reason = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=ResignationStatus.choices,
        default=ResignationStatus.SUBMITTED,
    )

    class Meta:
        ordering = ['-resignation_date']

    class RESAAS:
        label_field = "id"
        search_fields = ["employee__person__full_name", "status"]
        crud = True

    def __str__(self):
        return f"{self.employee} resignation ({self.status})"
