from django_resaas.core.base.serializers import BaseSerializer
from rh.models.contrato import Contrato
from rest_framework import serializers
from rh.serializers.funcionario import FuncionarioSerializer
from rh.models.funcionario import Funcionario

class ContratoSerializer(BaseSerializer):
        
    funcionario_id = serializers.PrimaryKeyRelatedField(
        source="funcionario", queryset=Funcionario.objects.all(), write_only=True
    )
    funcionario = FuncionarioSerializer(read_only=True)

    class Meta:
        model = Contrato
        fields = "__all__"
    