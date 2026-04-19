
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.examemedico import Examemedico
from saude.serializers.examemedico import ExamemedicoSerializer


@registerView('examemedicos')
class ExamemedicoAPIView(BaseAPIView):
    queryset = Examemedico.objects.all()   
    serializer_class = ExamemedicoSerializer
    
