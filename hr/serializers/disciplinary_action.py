# hr/serializers/disciplinary_action.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.disciplinary_case import DisciplinaryCase
from hr.models.disciplinary_action import DisciplinaryAction


class DisciplinaryActionSerializer(BaseSerializer):

    case = serializers.PrimaryKeyRelatedField(queryset=DisciplinaryCase.objects.all())
    case_data = serializers.SerializerMethodField()

    class Meta:
        model = DisciplinaryAction
        fields = "__all__"

    def get_case_data(self, obj):
        return {"id": obj.case_id, "label": str(obj.case)}

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None

        case = attrs.get("case")
        if entity_id and case is not None and str(case.entity_id) != str(entity_id):
            raise serializers.ValidationError({
                "case": "Does not belong to the current entity."
            })

        return attrs
