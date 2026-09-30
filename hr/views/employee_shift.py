# hr/views/employee_shift.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.employee_shift import EmployeeShift
from hr.serializers.employee_shift import EmployeeShiftSerializer


@registerView('employeeshifts', module='hr')
class EmployeeShiftAPIView(BaseAPIView):
    queryset = EmployeeShift.objects.all()
    serializer_class = EmployeeShiftSerializer