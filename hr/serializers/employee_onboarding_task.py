# hr/serializers/employee_onboarding_task.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.employee_onboarding import EmployeeOnboarding
from hr.models.employee_onboarding_task import EmployeeOnboardingTask


class EmployeeOnboardingTaskSerializer(BaseSerializer):

    onboarding = serializers.PrimaryKeyRelatedField(queryset=EmployeeOnboarding.objects.all())
    done_by_data = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeOnboardingTask
        fields = "__all__"
        # is_done/done_at/done_by only change through the complete_task/
        # reopen_task actions (hr/services/onboarding_service.py) - same
        # "workflow via actions, not free PATCH" rule as LeaveRequest.status.
        extra_kwargs = {
            'is_done': {'read_only': True},
            'done_at': {'read_only': True},
            'done_by': {'read_only': True},
        }

    def get_done_by_data(self, obj):
        if not obj.done_by_id:
            return None
        return {"id": obj.done_by_id, "label": str(obj.done_by)}
