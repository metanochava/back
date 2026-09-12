from django_resaas.saas.core.base.views import BaseAPIView, registerView

from saude.models.patient_identifier import PatientIdentifier
from saude.serializers.patient_identifier import PatientIdentifierSerializer


@registerView("patient_identifiers")
class PatientIdentifierAPIView(BaseAPIView):
    queryset = PatientIdentifier.objects.all()
    serializer_class = PatientIdentifierSerializer
