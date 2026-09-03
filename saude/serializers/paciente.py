from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.paciente import Paciente
from rest_framework import serializers
from django_resaas.engine.data.person.serializers.person import PersonSerializer
from django_resaas.engine.models.person import Person

class PacienteSerializer(BaseSerializer):
        
    person = serializers.PrimaryKeyRelatedField(
        queryset=Person.objects.all(), write_only=True
    )
    person_data = PersonSerializer(read_only=True)

    class Meta:
        model = Paciente
        fields = "__all__"

    