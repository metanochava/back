from django.db import models
from django_resaas.saas.core.base.models import BaseModel
from hr.models.attendance_source import AttendanceSource


class Attendance(BaseModel):
    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='attendances'
    )

    date = models.DateField()

    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)

    source = models.CharField(
        max_length=20,
        choices=AttendanceSource.choices,
        default=AttendanceSource.MANUAL,
    )

    # =========================
    # 📊 CALCULATED
    # =========================
    late_minutes = models.IntegerField(default=0)
    early_departure_minutes = models.IntegerField(default=0)
    overtime_minutes = models.IntegerField(default=0)
    worked_minutes = models.IntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=[
            ('present', 'Present'),
            ('absent', 'Absent'),
            ('late', 'Late')
        ],
        default='present'
    )

    class Meta:
        unique_together = ('employee', 'date')

    class RESAAS:
        label_field = "employee__person__full_name"
        search_fields = ["employee__person__full_name", "status"]
        crud = True

    def __str__(self):
        return f"{self.employee} - {self.date} ({self.status})"
