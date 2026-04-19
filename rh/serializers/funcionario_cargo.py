from django_resaas.core.base.serializers import BaseSerializer
from rh.models.funcionario_cargo import FuncionarioCargo
from rest_framework import serializers
from rh.models.funcionario import Funcionario
from rh.serializers.funcionario import FuncionarioSerializer
from rh.models.cargo import Cargo
from rh.serializers.cargo import CargoSerializer

class FuncionarioCargoSerializer(BaseSerializer):
        
    funcionario_id = serializers.PrimaryKeyRelatedField(
        source="funcionario", queryset=Funcionario.objects.all(), write_only=True
    )
    funcionario = FuncionarioSerializer(read_only=True)
    
    cargo_id = serializers.PrimaryKeyRelatedField(
        source="cargo", queryset=Cargo.objects.all(), write_only=True
    )
    cargo = CargoSerializer(read_only=True)

    class Meta:
        model = FuncionarioCargo
        fields = "__all__"
    