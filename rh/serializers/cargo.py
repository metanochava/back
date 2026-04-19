from django_resaas.core.base.serializers import BaseSerializer
from rh.models.cargo import Cargo
from rest_framework import serializers
from rh.models.departamento import Departamento
from rh.serializers.departamento import DepartamentoSerializer

class CargoSerializer(BaseSerializer):
        
    departamento_id = serializers.PrimaryKeyRelatedField(
        source="departamento", queryset=Departamento.objects.all(), write_only=True
    )
    departamento = DepartamentoSerializer(read_only=True)

    class Meta:
        model = Cargo
        fields = "__all__"
    