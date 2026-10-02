# hr/views/department.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.department import Department
from hr.serializers.department import DepartmentSerializer


@registerView('departments', module='hr')
class DepartmentAPIView(BaseAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer