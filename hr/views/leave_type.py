# hr/views/leave_type.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.leave_type import LeaveType
from hr.serializers.leave_type import LeaveTypeSerializer


@registerView('leavetypes', module='hr')
class LeaveTypeAPIView(BaseAPIView):
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
