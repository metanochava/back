from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView

from saude.models.internamento import Internamento
from saude.serializers.internamento import InternamentoSerializer


@registerView("internamentos")
class InternamentoAPIView(BaseAPIView):

    queryset = Internamento.objects.all()
    serializer_class = InternamentoSerializer
