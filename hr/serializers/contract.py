# hr/serializers/contract.py

from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.contract import Contract
from hr.models.employee import Employee

from hr.serializers.employee import EmployeeSerializer


class ContractSerializer(BaseSerializer):

    employee = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        write_only=True
    )

    employee_data = EmployeeSerializer(
        source='employee',
        read_only=True
    )

    class Meta:
        model = Contract
        fields = "__all__"

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
