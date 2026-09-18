from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.paciente import Paciente
from rest_framework import serializers
from django_resaas.saas.data.person.serializers.person import PersonSerializer
from django_resaas.saas.models.person import Person

class PacienteSerializer(BaseSerializer):
        
    person = serializers.PrimaryKeyRelatedField(
        queryset=Person.objects.all(), write_only=True
    )
    # Same "xxx_data" convention as EmployeeSerializer.person_data. It
    # used to be declared without source= (so it resolved to a
    # non-existent Paciente.person_data attribute and was silently
    # dropped from every response) - the edit/view pages need the
    # nested Person to show and edit its data.
    person_data = PersonSerializer(source='person', read_only=True)

    class Meta:
        model = Paciente
        fields = "__all__"

    