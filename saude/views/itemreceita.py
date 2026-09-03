from django_resaas.engine.core.base.views import BaseAPIView
from django_resaas.engine.core.base.views import registerView

from saude.models.itemreceita import ItemReceita
from saude.serializers.itemreceita import ItemReceitaSerializer


@registerView('itemreceitas')
class ItemReceitaAPIView(BaseAPIView):
    queryset = ItemReceita.objects.all()
    serializer_class = ItemReceitaSerializer