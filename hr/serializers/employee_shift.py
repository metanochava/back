# hr/serializers/employee_shift.py

from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.employee_shift import EmployeeShift
from hr.models.employee import Employee
from hr.models.shift import Shift

from hr.serializers.employee import EmployeeSerializer
from hr.serializers.shift import ShiftSerializer


class EmployeeShiftSerializer(BaseSerializer):

    employee = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        write_only=True
    )

    employee_data = EmployeeSerializer(
        source='employee',
        read_only=True
    )

    shift = serializers.PrimaryKeyRelatedField(
        queryset=Shift.objects.all(),
        write_only=True
    )

    shift_data = ShiftSerializer(
        source='shift',
        read_only=True
    )

    class Meta:
        model = EmployeeShift
        fields = "__all__"