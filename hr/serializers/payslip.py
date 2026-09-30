# hr/serializers/payslip.py

from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.payslip import Payslip
from hr.models.payroll import Payroll

from hr.serializers.payroll import PayrollSerializer


class PayslipSerializer(BaseSerializer):

    payroll = serializers.PrimaryKeyRelatedField(
        queryset=Payroll.objects.all(),
        write_only=True
    )

    payroll_data = PayrollSerializer(
        source='payroll',
        read_only=True
    )

    class Meta:
        model = Payslip
        fields = "__all__"