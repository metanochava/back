from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.dadovital import DadoVital
from saude.services import vital_signs_service
from rest_framework import serializers

class DadoVitalSerializer(BaseSerializer):

    class Meta:
        model = DadoVital
        fields = "__all__"
        # the professional is the one signed in (vital_signs_service.prepare_create)
        read_only_fields = ["employee"]
        # with an appointment the patient comes from it (validate() below)
        extra_kwargs = {"paciente": {"required": False}}

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None and not attrs.get("agenda") and not attrs.get("paciente"):
            raise serializers.ValidationError({"paciente": ["This field is required."]})
        # partial updates: check the values as they will be stored
        merged = {**({f: getattr(self.instance, f) for f in vital_signs_service.LIMITS} if self.instance else {}), **attrs}
        errors = vital_signs_service.validate_values(merged)
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
