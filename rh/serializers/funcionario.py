# rh/api/serializers/funcionario.py

from django_resaas.core.base.serializers import BaseSerializer
from rh.models.funcionario import Funcionario

class FuncionarioSerializer(BaseSerializer):
    class Meta:
        model = Funcionario
        fields = "__all__"