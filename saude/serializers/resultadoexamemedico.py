

from rest_framework import serializers
from django_resaas.core.base.serializers import BaseSerializer
from saude.models.resultadoexamemedico import ResultadoExameMedico


class ResultadoExameMedicoSerializer(BaseSerializer):

    class Meta:
        model = ResultadoExameMedico
        fields = "__all__"
