
from django_resaas.saas.core.base.views import BaseAPIView
from django_resaas.saas.core.base.views import registerView
from django.db.models import Count, Prefetch, Q

from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.models.resultadoexamemedico import ResultadoExameMedico
from saude.serializers.itempedidoexamemedico import ItemPedidoExameMedicoSerializer
from rest_framework.decorators import action
from django_resaas.saas.models.entity import Entity
from django_resaas.saas.core.utils import make_qr_b64, make_barcode_b64, png_bytes_to_b64, PDF

import barcode
import qrcode

from rest_framework.response import Response

from django_resaas.saas.core.decorators.action import resaas_action
from saude.services import exam_request_service, lab_result_service


@registerView('itempedidoexamemedicos')
class ItemPedidoExameMedicoAPIView(BaseAPIView):
    # lab phase 17: the list measured 7 queries per row (every relation's
    # label, and the latest result); joined / prefetched once instead
    queryset = (
        ItemPedidoExameMedico.objects
        .select_related(
            "entity", "branch", "created_by", "updated_by", "collected_by", "exame",
            "pedido__paciente__person", "pedido__consulta__paciente__person",
        )
        .prefetch_related(Prefetch(
            "resultados",
            queryset=ResultadoExameMedico.objects.select_related(
                "entity", "branch", "created_by", "updated_by", "paciente__person",
                "emitido_por", "validado_por", "released_by", "pai",
            ).annotate(
                _children_count=Count("filhos", filter=Q(filhos__na_lixeira=False, filhos__deleted_at__isnull=True)),
            ).order_by("-numero_revisao"),
            to_attr="results_latest_first",
        ))
    )
    serializer_class = ItemPedidoExameMedicoSerializer
    
    # an exam with a validated result is never deleted (lab phase 16)
    def perform_destroy(self, instance):
        exam_request_service.forbid_deleting_item_with_validated_result(instance)
        super().perform_destroy(instance)

    # same action as BaseAPIView.hard_delete (re-declared: an override
    # without the decorator would drop the route); hard_delete_<model>
    @resaas_action(detail=True, methods=["delete"], url_path="hard_delete")
    def hard_delete(self, request, pk=None):
        instance = ItemPedidoExameMedico.all_objects.filter(
            pk=pk, entity_id=request.entity_id, branch_id=request.branch_id,
        ).first()
        if instance is not None:
            exam_request_service.forbid_deleting_item_with_validated_result(instance)
        return super().hard_delete(request, pk=pk)

    # estado_exame is read-only in the API (lab phase 9): the state only
    # changes through the laboratory actions below (collect, reject_sample,
    # start_processing, cancel), each with its own permission and audit.

    # ------------------------------------------------------------------
    # Laboratory workflow (saude/services/exam_request_service.py,
    # saude/services/lab_result_service.py). All PROTECTED: BaseAPIView
    # checks the permission of each action and get_object() keeps the
    # item inside the current Entity/Branch.
    # ------------------------------------------------------------------

    # data for the result dialog, not a menu entry (visible=False)
    @resaas_action(detail=True, methods=["get"], label="Result form", icon="science",
                   permission="view_itempedidoexamemedico", visible=False)
    def result_form(self, request, *args, **kwargs):
        """The exam's active parameters (+ applicable reference, current
        values) the dynamic result form is built from."""
        return Response(lab_result_service.form_schema(self.get_object()))

    @resaas_action(detail=True, methods=["post"], label="Record result", icon="edit_note")
    def record_result(self, request, *args, **kwargs):
        """{"values": {code: value}, "observacao"?, "laudo"?} - validated
        against the exam definition by the server."""
        item = self.get_object()
        lab_result_service.record_result(
            request, item, request.data.get("values"),
            observacao=request.data.get("observacao"), laudo=request.data.get("laudo"),
        )
        return Response(lab_result_service.form_schema(item))

    # same capability as record_result: entering a result, another form of it
    @resaas_action(detail=True, methods=["post"], label="Record report", icon="description",
                   permission="record_result_itempedidoexamemedico", visible=False)
    def record_report(self, request, *args, **kwargs):
        """Free-form result (multipart): valor_resultado?, laudo?, observacao?,
        file? - on the same result record as record_result."""
        item = self.get_object()
        lab_result_service.record_report(
            request, item,
            valor_resultado=request.data.get("valor_resultado"),
            laudo=request.data.get("laudo"),
            observacao=request.data.get("observacao"),
            file=request.FILES.get("file"),
        )
        # read again with the view's prefetch: refresh_from_db() would keep
        # the stale prefetched results (lab phase 17)
        item = self.get_queryset().get(pk=item.pk)
        return Response(self.get_serializer(item).data)

    @resaas_action(detail=True, methods=["post"], label="Collect", icon="colorize", autorequest=True)
    def collect(self, request, *args, **kwargs):
        item = exam_request_service.collect(request, self.get_object())
        return Response(self.get_serializer(item).data)

    @resaas_action(detail=True, methods=["post"], label="Reject sample", icon="block")
    def reject_sample(self, request, *args, **kwargs):
        item = exam_request_service.reject_sample(request, self.get_object(), request.data.get("reason"))
        return Response(self.get_serializer(item).data)

    # read-only audit trail of the exam (lab phase 11): who collected,
    # rejected (and why), processed, cancelled, validated, released, amended
    @resaas_action(detail=True, methods=["get"], label="Exam trail", icon="history",
                   permission="view_itempedidoexamemedico", visible=False)
    def trail(self, request, *args, **kwargs):
        return Response(exam_request_service.item_trail(request, self.get_object()))

    # start_processing_itempedidoexamemedico: collected -> processing
    @resaas_action(detail=True, methods=["post"], label="Start processing", icon="biotech", autorequest=True)
    def start_processing(self, request, *args, **kwargs):
        item = exam_request_service.start_processing(request, self.get_object())
        return Response(self.get_serializer(item).data)

    # cancel_itempedidoexamemedico: {"reason"} - any state before completed
    @resaas_action(detail=True, methods=["post"], label="Cancel exam", icon="cancel")
    def cancel(self, request, *args, **kwargs):
        item = exam_request_service.cancel(request, self.get_object(), request.data.get("reason"))
        return Response(self.get_serializer(item).data)
