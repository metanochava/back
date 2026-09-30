# hr/serializers/department.py

from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.department import Department
from hr.models.employee import Employee



class DepartmentSerializer(BaseSerializer):

    manager = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        write_only=True,
        required=False,
        allow_null=True
    )

    manager_data = serializers.SerializerMethodField()

    def get_manager_data(self, obj):

        if not obj.manager:
            return None

        from hr.serializers.employee import EmployeeSerializer

        return EmployeeSerializer(
            obj.manager,
            context=self.context
        ).data

    class Meta:
        model = Department
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None
        manager = attrs.get("manager")

        if entity_id and manager is not None and str(manager.entity_id) != str(entity_id):
            raise serializers.ValidationError({
                "manager": "Does not belong to the current entity."
            })

        return attrs