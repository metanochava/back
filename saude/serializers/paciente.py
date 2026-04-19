from django_resaas.core.base.serializers import BaseSerializer
from saude.models.paciente import Paciente
from rest_framework import serializers
from django_resaas.data.pessoa.serializers.pessoa import PessoaSerializer
from django_resaas.models.pessoa import Pessoa

class PacienteSerializer(BaseSerializer):
        
    pessoa_id = serializers.PrimaryKeyRelatedField(
        source="pessoa", queryset=Pessoa.objects.all(), write_only=True
    )
    pessoa = PessoaSerializer(read_only=True)

    class Meta:
        model = Paciente
        fields = "__all__"
    