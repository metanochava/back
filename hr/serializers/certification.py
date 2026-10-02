# hr/serializers/certification.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.employee import Employee
from hr.models.certification import Certification


class CertificationSerializer(BaseSerializer):

    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    employee_data = serializers.SerializerMethodField()

    class Meta:
        model = Certification
        fields = "__all__"

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
