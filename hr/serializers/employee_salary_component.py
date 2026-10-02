# hr/serializers/employee_salary_component.py

from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.employee_salary_component import EmployeeSalaryComponent
from hr.models.employee_salary import EmployeeSalary
from hr.models.salary_component import SalaryComponent

from hr.serializers.salary_component import SalaryComponentSerializer


class EmployeeSalaryComponentSerializer(BaseSerializer):

    employee_salary = serializers.PrimaryKeyRelatedField(
        queryset=EmployeeSalary.objects.all(),
        write_only=True
    )

    component = serializers.PrimaryKeyRelatedField(
        queryset=SalaryComponent.objects.all(),
        write_only=True
    )

    component_data = SalaryComponentSerializer(
        source='component',
        read_only=True
    )

    resolved_amount = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeSalaryComponent
        fields = "__all__"

    def get_resolved_amount(self, obj):
        return obj.resolved_amount()

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None

        if entity_id:
            for field_name in ("employee_salary", "component"):
                related = attrs.get(field_name)

                if related is not None and str(related.entity_id) != str(entity_id):
                    raise serializers.ValidationError({
                        field_name: "Does not belong to the current entity."
                    })

        return attrs
