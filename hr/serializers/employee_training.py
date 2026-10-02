# hr/serializers/employee_training.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.employee import Employee
from hr.models.training_session import TrainingSession
from hr.models.employee_training import EmployeeTraining


class EmployeeTrainingSerializer(BaseSerializer):

    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    employee_data = serializers.SerializerMethodField()

    session = serializers.PrimaryKeyRelatedField(queryset=TrainingSession.objects.all())
    session_data = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeTraining
        fields = "__all__"
        # status/completed_at only change through mark_completed/mark_failed
        # actions (hr/services/training_service.py) - same "workflow via
        # actions, not free PATCH" rule as LeaveRequest.status/EmployeeGoal.
        extra_kwargs = {
            'status': {'read_only': True},
            'completed_at': {'read_only': True},
        }

    def get_employee_data(self, obj):
        return {"id": obj.employee_id, "label": str(obj.employee)}

    def get_session_data(self, obj):
        return {"id": obj.session_id, "label": str(obj.session)}

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None

        if entity_id:
            for field_name in ("employee", "session"):
                related = attrs.get(field_name)

                if related is not None and str(related.entity_id) != str(entity_id):
                    raise serializers.ValidationError({
                        field_name: "Does not belong to the current entity."
                    })

        return attrs
