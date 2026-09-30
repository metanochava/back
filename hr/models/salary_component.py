from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class SalaryComponent(BaseModel):
    TYPE_CHOICES = [
        ('earning', 'Earning'),
        ('deduction', 'Deduction'),
        # Employer Contribution (pedido secção 38): tracked as a
        # PayrollItem for costing/reporting but never subtracted from
        # net_salary - see hr/services/payroll_service.py.
        ('employer_contribution', 'Employer Contribution'),
    ]

    CALCULATION_CHOICES = [
        ('fixed', 'Fixed'),
        ('percentage', 'Percentage'),
        ('formula', 'Formula'),
    ]

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50)
    component_type = models.CharField(max_length=25, choices=TYPE_CHOICES)
    calculation_type = models.CharField(max_length=20, choices=CALCULATION_CHOICES, default='fixed')

    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    is_taxable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('entity', 'code')
        ordering = ['name']

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "code"]
        crud = True

    def __str__(self):
        return self.name