
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.classeexamemedico import Classeexamemedico
from saude.serializers.classeexamemedico import ClasseexamemedicoSerializer


@registerView('classeexamemedicos')
class ClasseexamemedicoAPIView(BaseAPIView):
    queryset = Classeexamemedico.objects.all()   
    serializer_class = ClasseexamemedicoSerializer
    
