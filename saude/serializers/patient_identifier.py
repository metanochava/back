from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.patient_identifier import PatientIdentifier


class PatientIdentifierSerializer(BaseSerializer):

    class Meta:
        model = PatientIdentifier
        fields = "__all__"
