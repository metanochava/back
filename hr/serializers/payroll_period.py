# hr/serializers/payroll_period.py

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.payroll_period import PayrollPeriod


class PayrollPeriodSerializer(BaseSerializer):

    class Meta:
        model = PayrollPeriod
        fields = "__all__"