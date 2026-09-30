# hr/views/payroll_item.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.payroll_item import PayrollItem
from hr.serializers.payroll_item import PayrollItemSerializer


@registerView('payrollitems', module='hr')
class PayrollItemAPIView(BaseAPIView):
    queryset = PayrollItem.objects.all()
    serializer_class = PayrollItemSerializer