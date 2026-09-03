from django_resaas.engine.core.base.views import BaseAPIView, registerView
from sales.models.customercontact import CustomerContact
from sales.serializers.customercontact import CustomerContactSerializer


@registerView("customercontacts")
class CustomerContactAPIView(BaseAPIView):
    queryset = CustomerContact.objects.all()
    serializer_class = CustomerContactSerializer
