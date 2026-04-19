from django_resaas.core.base.serializers import BaseSerializer
from clinica.models.pedido_exame_medico import PedidoExameMedico
from rest_framework import serializers

class PedidoExameMedicoSerializer(BaseSerializer):
    
    class Meta:
        model = PedidoExameMedico
        fields = "__all__"
    