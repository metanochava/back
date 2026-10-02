from django.db import models
from django_resaas.saas.core.base.models import BaseModel



class PayrollItem(BaseModel):
    payroll = models.ForeignKey(
        'hr.Payroll',
        on_delete=models.CASCADE,
        related_name='items'
    )

    component = models.ForeignKey(
        'hr.SalaryComponent',
        on_delete=models.CASCADE,
        related_name='payroll_items'
    )

    description = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['component__name']

    class RESAAS:
        label_field = "description"
        search_fields = ["description", "component__name"]
        crud = True

    def __str__(self):
        return f"{self.payroll} - {self.component}"