from django_resaas.core.base.serializers import BaseSerializer
from saude.models.pedidoexamemedico import Pedidoexamemedico
from rest_framework import serializers

class PedidoexamemedicoSerializer(BaseSerializer):
    
    class Meta:
        model = Pedidoexamemedico
        fields = "__all__"
    