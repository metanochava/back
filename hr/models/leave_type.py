# hr/models/leave_type.py

from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class LeaveType(BaseModel):
    """Annual/Sick/Maternity/... - each Entity defines its own set
    (pedido secção 24: not a hardcoded global choices list).

    Fase 3 keeps policy inline on LeaveType (default_days_per_year) instead
    of a separate LeavePolicy model: accrual/expiry/minimum-notice rules
    are real future needs, but nothing in this phase's scope (submit/
    approve/reject a request against a ledger balance) requires them yet -
    a second model with no consumer would just be an empty model (regra
    #113). Split LeavePolicy out if/when a phase actually needs those
    extra rules.
    """

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30, blank=True)

    is_paid = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=True)

    # Null = no automatic yearly allocation (e.g. unpaid leave, which is
    # also not balance-checked - see leave_service.requires_balance_check).
    default_days_per_year = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['name']
        unique_together = ('entity', 'code')

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "code"]
        crud = True

    def __str__(self):
        return self.name
