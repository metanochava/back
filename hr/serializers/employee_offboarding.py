# hr/serializers/employee_offboarding.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.employee import Employee
from hr.models.employee_offboarding import EmployeeOffboarding
from hr.serializers.employee_offboarding_task import (
    EmployeeOffboardingTaskSerializer,
)
from hr.services.lifecycle_service import offboarding_progress


class EmployeeOffboardingSerializer(BaseSerializer):

    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    employee_data = serializers.SerializerMethodField()

    tasks = EmployeeOffboardingTaskSerializer(many=True, read_only=True)
    progress = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeOffboarding
        fields = "__all__"
        extra_kwargs = {
            'status': {'read_only': True},
            'started_at': {'read_only': True},
            'completed_at': {'read_only': True},
        }

    def get_employee_data(self, obj):
        return {"id": obj.employee_id, "label": str(obj.employee)}

    def get_progress(self, obj):
        return offboarding_progress(obj)
