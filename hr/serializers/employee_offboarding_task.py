# hr/serializers/employee_offboarding_task.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.employee_offboarding import EmployeeOffboarding
from hr.models.employee_offboarding_task import EmployeeOffboardingTask


class EmployeeOffboardingTaskSerializer(BaseSerializer):

    offboarding = serializers.PrimaryKeyRelatedField(queryset=EmployeeOffboarding.objects.all())
    done_by_data = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeOffboardingTask
        fields = "__all__"
        extra_kwargs = {
            'is_done': {'read_only': True},
            'done_at': {'read_only': True},
            'done_by': {'read_only': True},
        }

    def get_done_by_data(self, obj):
        if not obj.done_by_id:
            return None
        return {"id": obj.done_by_id, "label": str(obj.done_by)}
