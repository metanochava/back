from django.db import models
from django_resaas.saas.core.base.models import BaseModel
from django_resaas.saas.core.utils import upload_path


class Payslip(BaseModel):
    payroll = models.OneToOneField(
        'hr.Payroll',
        on_delete=models.CASCADE,
        related_name='payslip'
    )

    issued_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to=upload_path(), null=True, blank=True)

    class RESAAS:
        label_field = "payroll__employee__person__full_name"
        search_fields = ["payroll__employee__person__full_name"]
        crud = True

    def __str__(self):
        return f"Payslip - {self.payroll}"