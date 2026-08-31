from django_resaas.core.base.views import BaseAPIView, registerView
from sales.models.customer import Customer
from sales.serializers.customer import CustomerSerializer


@registerView("customers")
class CustomerAPIView(BaseAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
