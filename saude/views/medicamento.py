
from django_resaas.saas.core.base.views import BaseAPIView
from django_resaas.saas.core.decorators.action import resaas_action
from rest_framework.response import Response
from saude.services import prescription_service
from django_resaas.saas.core.base.views import registerView
from saude.models.medicamento import Medicamento
from saude.serializers.medicamento import MedicamentoSerializer


@registerView('medicamentos')
class MedicamentoAPIView(BaseAPIView):
    queryset = Medicamento.objects.all()   
    serializer_class = MedicamentoSerializer

    # What add_receitamedica prefills when this medication is chosen:
    # the dosage and quantity of its last prescription (prescription_service).
    @resaas_action(detail=True, methods=["get"], label="Prescription defaults", icon="medication",
                   permission="view_medicamento", visible=False)
    def prescription_defaults(self, request, *args, **kwargs):
        return Response(prescription_service.prescription_defaults(request, self.get_object()))

    # def perform_create(self, serializer):
    #     serializer.save()
    
