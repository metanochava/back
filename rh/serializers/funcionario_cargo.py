from django_resaas.core.base.serializers import BaseSerializer
from rh.models.funcionario_cargo import FuncionarioCargo
from rest_framework import serializers
from rh.models.funcionario import Funcionario
from rh.serializers.funcionario import FuncionarioSerializer
from rh.models.cargo import Cargo
from rh.serializers.cargo import CargoSerializer

class FuncionarioCargoSerializer(BaseSerializer):
        
    funcionario = serializers.PrimaryKeyRelatedField(
         queryset=Funcionario.objects.all(), write_only=True
    )
    funcionario_data = FuncionarioSerializer(read_only=True)
    
    cargo = serializers.PrimaryKeyRelatedField(
        queryset=Cargo.objects.all(), write_only=True
    )
    cargo_data = CargoSerializer(read_only=True)

    class Meta:
        model = FuncionarioCargo
        fields = "__all__"
    