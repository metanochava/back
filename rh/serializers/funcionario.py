from django_resaas.core.base.serializers import BaseSerializer
from rh.models.funcionario import Funcionario
from rest_framework import serializers
from django_resaas.data.pessoa.serializers.pessoa import PessoaSerializer
from django_resaas.models.pessoa import Pessoa

class FuncionarioSerializer(BaseSerializer):
        
    pessoa = serializers.PrimaryKeyRelatedField(
        queryset=Pessoa.objects.all(), write_only=True
    )
    pessoa_data = PessoaSerializer(read_only=True)

    class Meta:
        model = Funcionario
        fields = "__all__"
    