from django.db import models
from django_resaas.saas.core.base.models import BaseModel



class ShiftSchedule(BaseModel):
    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='schedule'
    )

    shift = models.ForeignKey(
        'hr.Shift',
        on_delete=models.CASCADE
    )

    date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=[
            ('scheduled', 'Scheduled'),
            ('off', 'Off'),
            ('leave', 'Leave')
        ],
        default='scheduled'
    )

    class Meta:
        unique_together = ('employee', 'date')
        ordering = ['-date']

    class RESAAS:
        label_field = "employee__person__full_name"
        search_fields = ["employee__person__full_name", "shift__name"]
        crud = True  # 👉 podes desativar se for automático

    def __str__(self):
        return f"{self.employee} - {self.date} ({self.shift})"