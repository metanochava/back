from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.patient_identifier import PatientIdentifier


class PatientIdentifierSerializer(BaseSerializer):

    class Meta:
        model = PatientIdentifier
        fields = "__all__"
