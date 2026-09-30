from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class ApplicationStatus(models.TextChoices):
    APPLIED = "applied", "Applied"
    SCREENING = "screening", "Screening"
    SHORTLISTED = "shortlisted", "Shortlisted"
    INTERVIEW = "interview", "Interview"
    OFFERED = "offered", "Offered"
    HIRED = "hired", "Hired"
    REJECTED = "rejected", "Rejected"
    WITHDRAWN = "withdrawn", "Withdrawn"


# Explicit state machine (same shape as hr/models/leave_request.py's
# ALLOWED_TRANSITIONS - pedido secção 87: no boolean flags, no going
# backwards out of a terminal state). Enforced in
# hr/services/recruitment_service.py, not here.
#
# INTERVIEW and HIRED are deliberately reachable only through their own
# dedicated actions (schedule_interview / hire - see recruitment_service.py)
# because both have a real side effect beyond flipping a status column
# (creating an Interview row; creating Person+Employee) - the generic
# `move` action never targets either of them.
ALLOWED_TRANSITIONS = {
    ApplicationStatus.APPLIED: {
        ApplicationStatus.SCREENING,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.SCREENING: {
        ApplicationStatus.SHORTLISTED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.SHORTLISTED: {
        ApplicationStatus.INTERVIEW,  # via schedule_interview only
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.INTERVIEW: {
        ApplicationStatus.INTERVIEW,  # a further interview round
        ApplicationStatus.OFFERED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.OFFERED: {
        ApplicationStatus.HIRED,  # via hire only
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.HIRED: set(),
    ApplicationStatus.REJECTED: set(),
    ApplicationStatus.WITHDRAWN: set(),
}

# Targets the generic `move` action is allowed to set directly - moving
# into INTERVIEW/HIRED always goes through their dedicated actions instead
# (see recruitment_service.move()).
MOVE_TARGETS = {
    ApplicationStatus.SCREENING,
    ApplicationStatus.SHORTLISTED,
    ApplicationStatus.OFFERED,
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
}


class Application(BaseModel):
    job_opening = models.ForeignKey(
        'hr.JobOpening',
        on_delete=models.CASCADE,
        related_name='applications',
    )

    candidate = models.ForeignKey(
        'hr.Candidate',
        on_delete=models.CASCADE,
        related_name='applications',
    )

    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.APPLIED,
    )

    # Set only by recruitment_service.hire() - never accepted from the
    # client (BaseSerializer/ApplicationSerializer forces it read_only,
    # same pattern LeaveRequest uses for status/days/approved_*).
    employee = models.ForeignKey(
        'hr.Employee',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='applications',
    )

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('job_opening', 'candidate')
        indexes = [
            models.Index(fields=['job_opening', 'status']),
        ]

    class RESAAS:
        label_field = "id"
        search_fields = ["candidate__full_name", "job_opening__title", "status"]
        crud = True

    def __str__(self):
        return f"{self.candidate} -> {self.job_opening} ({self.status})"
