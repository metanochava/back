# hr/serializers/leave_type.py

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.leave_type import LeaveType


class LeaveTypeSerializer(BaseSerializer):

    class Meta:
        model = LeaveType
        fields = "__all__"
