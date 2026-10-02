# hr/serializers/resignation.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.employee import Employee
from hr.models.resignation import Resignation


class ResignationSerializer(BaseSerializer):

    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    employee_data = serializers.SerializerMethodField()

    class Meta:
        model = Resignation
        fields = "__all__"
        # status only changes through accept/withdraw
        # (hr/services/lifecycle_service.py).
        extra_kwargs = {
            'status': {'read_only': True},
        }

    def get_employee_data(self, obj):
        return {"id": obj.employee_id, "label": str(obj.employee)}

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None

        employee = attrs.get("employee")
        if entity_id and employee is not None and str(employee.entity_id) != str(entity_id):
            raise serializers.ValidationError({
                "employee": "Does not belong to the current entity."
            })

        return attrs
