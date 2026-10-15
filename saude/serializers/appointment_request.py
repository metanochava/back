from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.appointment_request import AppointmentRequest


class AppointmentRequestSerializer(BaseSerializer):
    """Staff view: a request is changed only through its confirm / reject
    actions, never by editing its fields."""

    class Meta:
        model = AppointmentRequest
        fields = "__all__"
        read_only_fields = [
            "medico", "data", "hora_inicio", "hora_fim", "name", "phone", "email",
            "specialty", "reason", "status",
        ]
