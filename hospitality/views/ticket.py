from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action
from django_resaas.saas.core.utils import all

from hospitality import services
from hospitality.models import PrepTicket
from hospitality.serializers import PrepTicketSerializer


@registerView("preptickets")
class PrepTicketAPIView(BaseAPIView):
    """What the stations prepare (created from the tabs' orders, never by the
    client).

        GET  hospitality/preptickets/kitchen/?station=   the tickets to prepare / serve
        POST hospitality/preptickets/{id}/advance/       {status: preparing|ready|served}
    """

    queryset = PrepTicket.objects.select_related("station", "table").all()
    serializer_class = PrepTicketSerializer
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        from rest_framework.exceptions import MethodNotAllowed
        raise MethodNotAllowed("POST")

    @resaas_action(methods=["get"], detail=False, label="Kitchen", icon="soup_kitchen",
                   tooltip="What the stations have to prepare and serve", visible=False)
    def kitchen(self, request):
        return all(request, data=services.kitchen(entity_id=request.entity_id, branch_id=request.branch_id,
                                                  station_id=request.query_params.get("station") or None))

    @resaas_action(methods=["post"], detail=True, label="Next step", icon="arrow_forward",
                   tooltip="Preparing, ready or served", visible=False)
    def advance(self, request, pk=None):
        try:
            ticket = services.advance_ticket(ticket=self.get_object(), status=request.data.get("status"),
                                             user=request.user)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.message_dict if hasattr(exc, "error_dict") else exc.messages)
        return all(request, data={"id": str(ticket.id), "status": ticket.status})
