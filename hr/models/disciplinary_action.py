from django.db import models
from django.utils import timezone
from django_resaas.saas.core.base.models import BaseModel
from hr.models.disciplinary_action_type import DisciplinaryActionType


class DisciplinaryAction(BaseModel):
    """A concrete action taken within a DisciplinaryCase - as sensitive as
    its parent (pedido secção 41), gated by its own dedicated permissions
    the same way."""

    case = models.ForeignKey(
        'hr.DisciplinaryCase',
        on_delete=models.CASCADE,
        related_name='actions',
    )

    action_type = models.CharField(
        max_length=30,
        choices=DisciplinaryActionType.choices,
        default=DisciplinaryActionType.OTHER,
    )

    issued_by = models.ForeignKey(
        'django_resaas.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    issued_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-issued_at']

    class RESAAS:
        label_field = "id"
        search_fields = ["case__employee__person__full_name", "action_type"]
        crud = True

    def __str__(self):
        return f"{self.case} - {self.action_type}"
