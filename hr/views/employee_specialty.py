# hr/views/employee_specialty.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.employee_specialty import EmployeeSpecialty
from hr.serializers.employee_specialty import EmployeeSpecialtySerializer


@registerView('employeespecialtys', module='hr')
class EmployeeSpecialtyAPIView(BaseAPIView):
    queryset = EmployeeSpecialty.objects.all()
    serializer_class = EmployeeSpecialtySerializer