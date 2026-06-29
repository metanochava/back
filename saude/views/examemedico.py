
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.examemedico import ExameMedico
from saude.serializers.examemedico import ExameMedicoSerializer
from rest_framework.decorators import action


@registerView('examemedicos')
class ExameMedicoAPIView(BaseAPIView):
    queryset = ExameMedico.objects.all()   
    serializer_class = ExameMedicoSerializer
    
