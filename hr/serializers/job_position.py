from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.job_position import JobPosition
from hr.models.department import Department


class JobPositionSerializer(BaseSerializer):

    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        required=False,
        allow_null=True
    )

    department_data = serializers.SerializerMethodField()

    def get_department_data(self, obj):

        if not obj.department:
            return None

        return {
            "id": obj.department.id,
            # RESAAS label (RESAAS.label_field), not a `label` attribute - the
            # models have none, which made every job position LIST answer 500
            "label": obj.department.get_label(),
            "name": getattr(obj.department, "name", None),
        }

    class Meta:
        model = JobPosition
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None
        department = attrs.get("department")

        if entity_id and department is not None and str(department.entity_id) != str(entity_id):
            raise serializers.ValidationError({
                "department": "Does not belong to the current entity."
            })

        return attrs