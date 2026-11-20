from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from django_resaas.saas.core.base.views import registerView
from django_resaas.saas.core.exceptions import ResaasAPIException
from django_resaas.saas.core.utils.full_path import FullPath

from hospitality import services


class _AddressThrottle(SimpleRateThrottle):
    """Per client address (a public page is abused by address)."""

    setting = None
    default_rate = None

    def get_rate(self):
        return getattr(settings, self.setting, self.default_rate)

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class TableQrReadThrottle(_AddressThrottle):
    scope = "hospitality_qr_read"
    setting = "HOSPITALITY_QR_READ_THROTTLE_RATE"
    default_rate = "600/hour"


class TableQrCallThrottle(_AddressThrottle):
    scope = "hospitality_qr_call"
    setting = "HOSPITALITY_QR_CALL_THROTTLE_RATE"
    default_rate = "30/hour"


class TableQrOrderThrottle(_AddressThrottle):
    scope = "hospitality_qr_order"
    setting = "HOSPITALITY_QR_ORDER_THROTTLE_RATE"
    default_rate = "20/hour"


@registerView("qr")
class TableQrViewSet(viewsets.ViewSet):
    """The page a table's QR code opens (no session).

    PUBLIC (explicit): the table - and so its Entity - comes only from its
    secret token, never from the client; an unknown, inactive or rotated
    token, or the module inactive for the Entity, is 404. Throttled per
    client address; GET never writes.

        GET  hospitality/qr/<token>/        the place, the table, the menu, the open tab's total
        POST hospitality/qr/<token>/call/   {kind: waiter|bill} -> 201 new, 202 already waiting
        POST hospitality/qr/<token>/order/  {client_key, lines: [{product_id, quantidade}], note?}
                                            -> 201 waiting for staff, 202 the same client_key again
    """

    permission_classes = (permissions.AllowAny,)
    lookup_value_regex = r"[A-Za-z0-9_\-]{1,64}"

    def get_throttles(self):
        if self.action == "call":
            return [TableQrCallThrottle()]
        if self.action == "order":
            return [TableQrOrderThrottle()]
        return [TableQrReadThrottle()]

    @staticmethod
    def _table(token):
        table = services.table_for_token(token)
        if table is None:
            raise ResaasAPIException("This table was not found.", code="table_not_found",
                                     status_code=status.HTTP_404_NOT_FOUND)
        return table

    def retrieve(self, request, pk=None):
        table = self._table(pk)
        image_url = lambda file: FullPath.url(request, file.url, temporary=False)  # noqa: E731
        return Response(services.public_page(table, image_url=image_url))

    @action(detail=True, methods=["post"])
    def call(self, request, pk=None):
        table = self._table(pk)
        try:
            table_request, created = services.call(table, request.data.get("kind"))
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.message_dict if hasattr(exc, "error_dict") else exc.messages)
        return Response({"kind": table_request.kind, "status": table_request.status},
                        status=status.HTTP_201_CREATED if created else status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def order(self, request, pk=None):
        table = self._table(pk)
        try:
            order, created = services.place_order(table, request.data.get("client_key"), request.data.get("lines"),
                                                  request.data.get("note") or "")
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.message_dict if hasattr(exc, "error_dict") else exc.messages)
        return Response(services._order_data(order),
                        status=status.HTTP_201_CREATED if created else status.HTTP_202_ACCEPTED)
