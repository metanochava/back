# hr/views/salary_component.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.salary_component import SalaryComponent
from hr.serializers.salary_component import SalaryComponentSerializer


@registerView('salarycomponents', module='hr')
class SalaryComponentAPIView(BaseAPIView):
    queryset = SalaryComponent.objects.all()
    serializer_class = SalaryComponentSerializer