from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action
from django_resaas.saas.core.utils import PDF, all

from hospitality import services
from hospitality.models import DiningTable
from hospitality.serializers import DiningTableSerializer


def _drf(exc):
    return DRFValidationError(exc.message_dict if hasattr(exc, "error_dict") else exc.messages)


@registerView("diningtables")
class DiningTableAPIView(BaseAPIView):
    """The branch's tables (CRUD) and what the point of sale does with them.

        GET  hospitality/diningtables/board/            the tables with their state, tab and requests
        POST hospitality/diningtables/{id}/start_tab/   the table's open tab (opened when it has none)
        POST hospitality/diningtables/{id}/rotate_qr/   a new QR secret (the printed code stops working)
        GET  hospitality/diningtables/qr_cards/?ids=    PDF: one QR card per table
    """

    queryset = DiningTable.objects.select_related("area").all()
    serializer_class = DiningTableSerializer

    @resaas_action(methods=["get"], detail=False, label="Board", icon="table_bar",
                   tooltip="The tables with their state, open tab and requests", visible=False)
    def board(self, request):
        return all(request, data=services.board(entity_id=request.entity_id, branch_id=request.branch_id))

    @resaas_action(methods=["post"], detail=True, label="Start tab", icon="add_task",
                   tooltip="The table's open tab (opened when it has none)", visible=False)
    def start_tab(self, request, pk=None):
        try:
            sale_id = services.start_tab(table=self.get_object(), user=request.user)
        except DjangoValidationError as exc:
            raise _drf(exc)
        return all(request, data={"tab": str(sale_id)})

    @resaas_action(methods=["post"], detail=True, label="New QR code", icon="qr_code_2",
                   tooltip="A new QR code for the table: the printed one stops working", position="t", order=20)
    def rotate_qr(self, request, pk=None):
        table = services.rotate_qr(table=self.get_object(), user=request.user)
        return all(request, data=self.get_serializer(table).data)

    # the record's PDF (the list row's PDF button) is the table's QR card, and
    # the list's PDF the cards of the listed tables - not the generic sheets
    @resaas_action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None, *args, **kwargs):
        table = self.get_object()
        context = services.qr_cards_context(request, [table])
        return PDF("hospitality/pdf/table_cards.html", request, pdf_person=table.name, **context)

    @resaas_action(detail=False, methods=["get"], url_path="pdf_list")
    def pdf_list(self, request, *args, **kwargs):
        tables = self.filter_queryset(self.get_queryset()).filter(active=True)
        context = services.qr_cards_context(request, tables.order_by("area__order", "order", "name"))
        return PDF("hospitality/pdf/table_cards.html", request, **context)

    @resaas_action(methods=["get"], detail=False, label="QR cards", icon="print",
                   tooltip="Print the tables' QR cards", position="l", order=10)
    def qr_cards(self, request):
        """PDF (GET, nothing is written): the cards of ?ids=<id>,<id> or of
        every active table of the branch."""
        tables = self.get_queryset().filter(active=True).select_related("entity", "entity__entity_type")
        ids = [i for i in (request.query_params.get("ids") or "").split(",") if i.strip()]
        if ids:
            try:
                tables = tables.filter(id__in=ids)
            except (ValueError, DjangoValidationError):
                raise DRFValidationError({"ids": ["Enter valid ids."]})
        context = services.qr_cards_context(request, tables.order_by("area__order", "order", "name"))
        return PDF("hospitality/pdf/table_cards.html", request, **context)
