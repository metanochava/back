from django_resaas.core.base.serializers import BaseSerializer
from saude.models.medico import Medico
from rest_framework import serializers


class MedicoSerializer(BaseSerializer):

    class Meta:
        model = Medico
        fields = "__all__"