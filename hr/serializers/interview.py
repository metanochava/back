# hr/serializers/interview.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.application import Application
from hr.models.employee import Employee
from hr.models.interview import Interview


class InterviewSerializer(BaseSerializer):

    application = serializers.PrimaryKeyRelatedField(
        queryset=Application.objects.all(),
        write_only=True,
    )
    application_data = serializers.SerializerMethodField()

    interviewer = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    interviewer_data = serializers.SerializerMethodField()

    class Meta:
        model = Interview
        fields = "__all__"

    def get_application_data(self, obj):
        return {"id": obj.application_id, "label": str(obj.application)}

    def get_interviewer_data(self, obj):
        if not obj.interviewer_id:
            return None
        return {"id": obj.interviewer_id, "label": str(obj.interviewer)}

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None

        if entity_id:
            for field_name in ("application", "interviewer"):
                related = attrs.get(field_name)

                if related is not None and str(related.entity_id) != str(entity_id):
                    raise serializers.ValidationError({
                        field_name: "Does not belong to the current entity."
                    })

        return attrs
