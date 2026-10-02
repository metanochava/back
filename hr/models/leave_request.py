# hr/models/leave_request.py

from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class LeaveRequestStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


# Explicit state machine (pedido secção 87: no boolean flags, no
# REJECTED -> APPROVED). Enforced in hr/services/leave_service.py, not
# here - a model has no natural place to reject an invalid transition
# with a field-attributed DRF error.
ALLOWED_TRANSITIONS = {
    LeaveRequestStatus.DRAFT: {LeaveRequestStatus.PENDING, LeaveRequestStatus.CANCELLED},
    LeaveRequestStatus.PENDING: {
        LeaveRequestStatus.APPROVED,
        LeaveRequestStatus.REJECTED,
        LeaveRequestStatus.CANCELLED,
    },
    # An already-approved request can still be cancelled (e.g. the
    # employee no longer needs the days) - leave_service.cancel() reverses
    # the ledger usage entry it created on approval. It can NOT go back to
    # PENDING/REJECTED - cancellation is terminal, same as REJECTED.
    LeaveRequestStatus.APPROVED: {LeaveRequestStatus.CANCELLED},
    LeaveRequestStatus.REJECTED: set(),
    LeaveRequestStatus.CANCELLED: set(),
}


class LeaveRequest(BaseModel):
    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='leave_requests',
    )

    leave_type = models.ForeignKey(
        'hr.LeaveType',
        on_delete=models.PROTECT,
        related_name='leave_requests',
    )

    start_date = models.DateField()
    end_date = models.DateField()

    # Business days (weekdays minus holidays - see
    # leave_service.calculate_business_days) covered by this request.
    # Computed by the service on create/submit, never accepted from the
    # client directly (BaseSerializer already forces it read_only the same
    # way it does id/entity/branch/... - see LeaveRequestSerializer).
    days = models.PositiveIntegerField(default=0)

    reason = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=LeaveRequestStatus.choices,
        default=LeaveRequestStatus.DRAFT,
    )

    approved_by = models.ForeignKey(
        'django_resaas.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='leave_requests_approved',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    class RESAAS:
        label_field = "id"
        search_fields = ["employee__person__full_name", "leave_type__name", "status"]
        crud = True

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.start_date}..{self.end_date})"
