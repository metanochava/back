# hr/views/attendance.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.attendance import Attendance
from hr.serializers.attendance import AttendanceSerializer


@registerView('attendances', module='hr')
class AttendanceAPIView(BaseAPIView):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer