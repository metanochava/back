# hr/serializers/termination.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.employee import Employee
from hr.models.termination import Termination


class TerminationSerializer(BaseSerializer):

    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    employee_data = serializers.SerializerMethodField()

    class Meta:
        model = Termination
        fields = "__all__"

    def get_employee_data(self, obj):
        return {"id": obj.employee_id, "label": str(obj.employee)}
