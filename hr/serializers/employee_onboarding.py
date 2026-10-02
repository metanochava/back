# hr/serializers/employee_onboarding.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.employee import Employee
from hr.models.employee_onboarding import EmployeeOnboarding
from hr.models.onboarding_template import OnboardingTemplate
from hr.serializers.employee_onboarding_task import (
    EmployeeOnboardingTaskSerializer,
)
from hr.services.onboarding_service import progress as compute_progress


class EmployeeOnboardingSerializer(BaseSerializer):

    employee = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), write_only=True,
    )
    employee_data = serializers.SerializerMethodField()

    template = serializers.PrimaryKeyRelatedField(
        queryset=OnboardingTemplate.objects.all(), required=False, allow_null=True,
    )
    template_data = serializers.SerializerMethodField()

    tasks = EmployeeOnboardingTaskSerializer(many=True, read_only=True)
    progress = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeOnboarding
        fields = "__all__"
        # Only start_onboarding/complete_onboarding/cancel_onboarding
        # (hr/services/onboarding_service.py) may change these.
        extra_kwargs = {
            'status': {'read_only': True},
            'started_at': {'read_only': True},
            'completed_at': {'read_only': True},
        }

    def get_employee_data(self, obj):
        return {"id": obj.employee_id, "label": str(obj.employee)}

    def get_template_data(self, obj):
        if not obj.template_id:
            return None
        return {"id": obj.template_id, "label": str(obj.template)}

    def get_progress(self, obj):
        return compute_progress(obj)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None

        if entity_id:
            for field_name in ("employee", "template"):
                related = attrs.get(field_name)

                if related is not None and str(related.entity_id) != str(entity_id):
                    raise serializers.ValidationError({
                        field_name: "Does not belong to the current entity."
                    })

        return attrs
