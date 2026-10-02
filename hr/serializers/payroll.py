# hr/serializers/payroll.py

from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.payroll import Payroll
from hr.models.employee import Employee
from hr.models.payroll_period import PayrollPeriod

from hr.serializers.employee import EmployeeSerializer
from hr.serializers.payroll_period import PayrollPeriodSerializer


class PayrollSerializer(BaseSerializer):

    employee = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        write_only=True
    )

    employee_data = EmployeeSerializer(
        source='employee',
        read_only=True
    )

    period = serializers.PrimaryKeyRelatedField(
        queryset=PayrollPeriod.objects.all(),
        write_only=True
    )

    period_data = PayrollPeriodSerializer(
        source='period',
        read_only=True
    )

    # Payslip is a reverse OneToOne (only exists once confirm_payroll has
    # run - see hr/services/payroll_service.py) - not a real model field,
    # so it can't go through Meta.fields="__all__" like the rest; exposed
    # read-only for PayrollRunPage.vue's "view payslip PDF" button.
    payslip_id = serializers.SerializerMethodField()

    def get_payslip_id(self, obj):
        payslip = getattr(obj, 'payslip', None)
        return payslip.id if payslip else None

    class Meta:
        model = Payroll
        fields = "__all__"
        # Only calculate_payroll/review_payroll/confirm_payroll/mark_paid/
        # cancel_payroll (hr/services/payroll_service.py) may change these -
        # a free PATCH here would bypass the state machine and the
        # snapshot-immutability guarantee for a confirmed payroll.
        extra_kwargs = {
            'status': {'read_only': True},
            'gross_salary': {'read_only': True},
            'total_earnings': {'read_only': True},
            'total_deductions': {'read_only': True},
            'net_salary': {'read_only': True},
            'calculated_at': {'read_only': True},
            'confirmed_at': {'read_only': True},
            'paid_at': {'read_only': True},
        }