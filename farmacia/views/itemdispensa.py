from django_resaas.engine.core.base.views import BaseAPIView, registerView
from farmacia.models.itemdispensa import ItemDispensa
from farmacia.serializers.itemdispensa import ItemDispensaSerializer


@registerView("itemdispensas")
class ItemDispensaAPIView(BaseAPIView):
    queryset = ItemDispensa.objects.all()
    serializer_class = ItemDispensaSerializer
