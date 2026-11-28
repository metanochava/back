from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.agenda import Agenda


class AgendaSerializer(BaseSerializer):
    # "Book now": the patient is here - the appointment is created for today
    # at the current time and checked in at once (waiting for vital signs).
    # Not a model field; AgendaAPIView.perform_create applies it.
    immediate = serializers.BooleanField(write_only=True, required=False, default=False)
    # reception: the draft sale of this appointment's consultation, or None
    # (clinical_billing_service.charge_of). Read only.
    charge = serializers.SerializerMethodField()

    def get_charge(self, obj):
        from saude.services import clinical_billing_service

        return clinical_billing_service.charge_of(clinical_billing_service.SOURCE_AGENDA, obj.id)

    class Meta:
        model = Agenda
        fields = "__all__"
