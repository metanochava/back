# hr/serializers/attendance.py

from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.attendance import Attendance
from hr.models.employee import Employee

from hr.serializers.employee import EmployeeSerializer


class AttendanceSerializer(BaseSerializer):

    employee = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        write_only=True
    )

    employee_data = EmployeeSerializer(
        source='employee',
        read_only=True
    )

    class Meta:
        model = Attendance
        fields = "__all__"