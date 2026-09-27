from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.appointment_request import AppointmentRequest


class PublicAppointmentRequestSerializer(serializers.Serializer):
    """What a visitor sends from the public site. Entity, Branch, status and
    the end time are never fields: they come from the Origin and the
    doctor's schedule (public_booking_service)."""

    doctor = serializers.CharField()
    date = serializers.DateField()
    time = serializers.RegexField(r"^\d{2}:\d{2}$")
    name = serializers.CharField(max_length=150, trim_whitespace=True)
    phone = serializers.CharField(max_length=30, trim_whitespace=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    # the id of one of the doctor's specialties (hr.Specialty); the title is stored
    specialty = serializers.CharField(max_length=64, required=False, allow_blank=True)
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    # honeypot: hidden in the form, so only bots fill it in
    website = serializers.CharField(required=False, allow_blank=True)


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
