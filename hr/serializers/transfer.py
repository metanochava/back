# hr/serializers/transfer.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from django_resaas.saas.models.branch import Branch

from hr.models.employee import Employee
from hr.models.department import Department
from hr.models.job_position import JobPosition
from hr.models.transfer import Transfer


class TransferSerializer(BaseSerializer):

    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    employee_data = serializers.SerializerMethodField()

    to_branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    to_branch_data = serializers.SerializerMethodField()

    to_department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True,
    )
    to_position = serializers.PrimaryKeyRelatedField(
        queryset=JobPosition.objects.all(), required=False, allow_null=True,
    )

    class Meta:
        model = Transfer
        fields = "__all__"

    def get_employee_data(self, obj):
        return {"id": obj.employee_id, "label": str(obj.employee)}

    def get_to_branch_data(self, obj):
        return {"id": obj.to_branch_id, "label": str(obj.to_branch)}
