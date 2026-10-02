# hr/views/employee_salary_component.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.employee_salary_component import EmployeeSalaryComponent
from hr.serializers.employee_salary_component import EmployeeSalaryComponentSerializer


@registerView('employeesalarycomponents', module='hr')
class EmployeeSalaryComponentAPIView(BaseAPIView):
    queryset = EmployeeSalaryComponent.objects.all()
    serializer_class = EmployeeSalaryComponentSerializer
