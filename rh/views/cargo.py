# rh/api/views/cargo.py

from django_resaas.core.base.views import BaseAPIView, registerView
from rh.models.cargo import Cargo
from rh.serializers.cargo import CargoSerializer

@registerView(module="rh")
class CargoAPIView(BaseAPIView):
    queryset = Cargo.objects.all()
    serializer_class = CargoSerializer