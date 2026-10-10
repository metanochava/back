from django_resaas.saas.core.base.serializers import BaseSerializer
from rest_framework import serializers

from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.models.resultadoexamemedico import ResultadoExameMedico

from saude.serializers.resultadoexamemedico import ResultadoExameMedicoSerializer


class ItemPedidoExameMedicoSerializer(BaseSerializer):

    resultado = serializers.SerializerMethodField()

    class Meta:
        model = ItemPedidoExameMedico
        fields = "__all__"
        # the exam state changes only through the laboratory actions
        # (saude/services/exam_request_service.py), never by a PATCH
        read_only_fields = ["estado_exame"]

    def validate(self, attrs):
        """Lab phase 16: an exam item never moves to another request (that
        would move it - and its results - to another patient), and its exam
        changes only while nothing was done with it yet."""
        attrs = super().validate(attrs)
        item = self.instance
        if item is None:
            return attrs

        errors = {}
        if "pedido" in attrs and attrs["pedido"].pk != item.pedido_id:
            errors["pedido"] = ["An exam cannot be moved to another request."]
        if "exame" in attrs and attrs["exame"].pk != item.exame_id and (
            item.estado_exame not in ("pendente", "agendado") or item.resultados.exists()
        ):
            errors["exame"] = ["The exam cannot be changed after collection or a result."]
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_resultado(self, obj):

        # prefetched by the API view (lab phase 17); a plain query otherwise
        prefetched = getattr(obj, "results_latest_first", None)
        if prefetched is not None:
            resultado = prefetched[0] if prefetched else None
        else:
            resultado = obj.resultados.order_by("-numero_revisao").first()

        if resultado:
            return ResultadoExameMedicoSerializer(resultado).data

        return {
            "id": None,
            "valor_resultado": "",
            "laudo": "",
            "observacao": "",
            "file": None,
            "numero_revisao": 1,
            "validado": False,
            "assinado_digitalmente": False,
            "data_colheita": None,
            "data_resultado": None
        }