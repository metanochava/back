from django_resaas.saas.core.base.views import BaseAPIView
from saude.services.document_edit_policy import DocumentEditWindowMixin
from django_resaas.saas.core.base.views import registerView

from saude.models.itemreceita import ItemReceita
from saude.serializers.itemreceita import ItemReceitaSerializer


@registerView('itemreceitas')
# edited only by its author, within 24 h (document_edit_policy)
class ItemReceitaAPIView(DocumentEditWindowMixin, BaseAPIView):
    queryset = ItemReceita.objects.all()
    serializer_class = ItemReceitaSerializer