# hr/serializers/employee_goal.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.employee import Employee
from hr.models.performance_cycle import PerformanceCycle
from hr.models.employee_goal import EmployeeGoal


class EmployeeGoalSerializer(BaseSerializer):

    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    employee_data = serializers.SerializerMethodField()

    cycle = serializers.PrimaryKeyRelatedField(queryset=PerformanceCycle.objects.all())
    cycle_data = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeGoal
        fields = "__all__"
        # progress/status only change through the update_progress action
        # (hr/services/performance_service.py) - same "workflow via
        # actions, not free PATCH" rule as LeaveRequest.status.
        extra_kwargs = {
            'progress': {'read_only': True},
            'status': {'read_only': True},
        }

    def get_employee_data(self, obj):
        return {"id": obj.employee_id, "label": str(obj.employee)}

    def get_cycle_data(self, obj):
        return {"id": obj.cycle_id, "label": str(obj.cycle)}

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None

        if entity_id:
            for field_name in ("employee", "cycle"):
                related = attrs.get(field_name)

                if related is not None and str(related.entity_id) != str(entity_id):
                    raise serializers.ValidationError({
                        field_name: "Does not belong to the current entity."
                    })

        return attrs
