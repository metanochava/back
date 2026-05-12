from django_resaas.core.base.serializers import BaseSerializer
from rh.models.funcionario import Funcionario
from rest_framework import serializers
from django_resaas.data.person.serializers.person import PersonSerializer
from django_resaas.models.person import Person

class FuncionarioSerializer(BaseSerializer):
        
    person = serializers.PrimaryKeyRelatedField(
        queryset=Person.objects.all(), write_only=True
    )
    person_data = PersonSerializer(read_only=True)

    class Meta:
        model = Funcionario
        fields = "__all__"
    