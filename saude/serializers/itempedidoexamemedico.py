from django_resaas.engine.core.base.serializers import BaseSerializer
from rest_framework import serializers

from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.models.resultadoexamemedico import ResultadoExameMedico

from saude.serializers.resultadoexamemedico import ResultadoExameMedicoSerializer


class ItemPedidoExameMedicoSerializer(BaseSerializer):

    resultado = serializers.SerializerMethodField()

    class Meta:
        model = ItemPedidoExameMedico
        fields = "__all__"

    def get_resultado(self, obj):

        resultado = (
            obj.resultados
            .order_by("-numero_revisao")
            .first()
        )

        if resultado:
            return ResultadoExameMedicoSerializer(resultado).data

        return {
            "id": None,
            "valor_resultado": "",
            "laudo": "",
            "observacao": "",
            "ficheiro": None,
            "numero_revisao": 1,
            "validado": False,
            "assinado_digitalmente": False,
            "data_colheita": None,
            "data_resultado": None
        }