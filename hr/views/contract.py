# hr/views/contract.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.contract import Contract
from hr.serializers.contract import ContractSerializer


@registerView('contracts', module='hr')
class ContractAPIView(BaseAPIView):
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
