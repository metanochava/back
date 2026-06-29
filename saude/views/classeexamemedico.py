
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.classeexamemedico import ClasseExameMedico
from saude.serializers.classeexamemedico import ClasseExameMedicoSerializer


@registerView('classeexamemedicos')
class ClasseExameMedicoAPIView(BaseAPIView):
    queryset = ClasseExameMedico.objects.all()   
    serializer_class = ClasseExameMedicoSerializer
    
