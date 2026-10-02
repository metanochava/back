# hr/models/leave_balance_entry.py

from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class LeaveBalanceEntryType(models.TextChoices):
    ALLOCATION = "allocation", "Allocation"
    USAGE = "usage", "Usage"
    ADJUSTMENT = "adjustment", "Adjustment"
    EXPIRY = "expiry", "Expiry"


class LeaveBalanceEntry(BaseModel):
    """A ledger, not a decremented counter (pedido secção 26, explícito:
    "+ Annual allocation, - Approved leave, + Adjustment, - Expired days").
    An employee's current balance for a LeaveType is always the sum of
    their entries - see leave_service.current_balance() - never a field
    written to directly by any view."""

    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='leave_balance_entries',
    )

    leave_type = models.ForeignKey(
        'hr.LeaveType',
        on_delete=models.CASCADE,
        related_name='leave_balance_entries',
    )

    # Positive (allocation, adjustment credit) or negative (usage, expiry,
    # adjustment debit) - the sign IS the direction, no separate flag.
    amount = models.IntegerField()

    entry_type = models.CharField(
        max_length=20,
        choices=LeaveBalanceEntryType.choices,
    )

    # The LeaveRequest that produced this entry (usage entries created by
    # the `approve` action) - null for manual allocations/adjustments.
    reference = models.ForeignKey(
        'hr.LeaveRequest',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='balance_entries',
    )

    date = models.DateField()
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['employee', 'leave_type']),
        ]

    class RESAAS:
        label_field = "id"
        search_fields = ["employee__person__full_name", "leave_type__name", "entry_type"]
        crud = True

    def __str__(self):
        return f"{self.employee} / {self.leave_type}: {self.amount:+d} ({self.entry_type})"
