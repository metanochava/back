
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from rh.models.cargo import Cargo
from rh.serializers.cargo import CargoSerializer


@registerView('cargos')
class CargoAPIView(BaseAPIView):
    queryset = Cargo.objects.all()   
    serializer_class = CargoSerializer
    
