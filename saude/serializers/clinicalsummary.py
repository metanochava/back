from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from saude.models.clinicalsummary import ClinicalSummary


class ClinicalSummarySerializer(BaseSerializer):
    """The consultation is the server's (ClinicalSummaryAPIView.create:
    consultation_service.resolve_for_document), never the client's."""

    class Meta:
        model = ClinicalSummary
        fields = "__all__"
        read_only_fields = ["consulta"]

    # the doctor of the consultation, for the lists
    medico = serializers.SerializerMethodField()

    def get_medico(self, obj):
        employee = obj.consulta.employee
        return {"name": employee.person.full_name} if employee else None
