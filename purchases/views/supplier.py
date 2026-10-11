from django_resaas.saas.core.base.views import BaseAPIView, registerView

from purchases.models import Supplier
from purchases.serializers import SupplierSerializer


@registerView("suppliers")
class SupplierAPIView(BaseAPIView):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
