# hr/serializers/onboarding_template.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.department import Department
from hr.models.job_position import JobPosition
from hr.models.onboarding_template import OnboardingTemplate


class OnboardingTemplateSerializer(BaseSerializer):

    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True,
    )
    department_data = serializers.SerializerMethodField()

    position = serializers.PrimaryKeyRelatedField(
        queryset=JobPosition.objects.all(), required=False, allow_null=True,
    )
    position_data = serializers.SerializerMethodField()

    tasks_count = serializers.SerializerMethodField()

    class Meta:
        model = OnboardingTemplate
        fields = "__all__"

    def get_department_data(self, obj):
        if not obj.department_id:
            return None
        return {"id": obj.department_id, "label": str(obj.department)}

    def get_position_data(self, obj):
        if not obj.position_id:
            return None
        return {"id": obj.position_id, "label": str(obj.position)}

    def get_tasks_count(self, obj):
        return obj.tasks.count()

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None

        if entity_id:
            for field_name in ("department", "position"):
                related = attrs.get(field_name)

                if related is not None and str(related.entity_id) != str(entity_id):
                    raise serializers.ValidationError({
                        field_name: "Does not belong to the current entity."
                    })

        return attrs
