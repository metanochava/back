from django.conf import settings
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from django_resaas.saas.core.base.views import registerView
from django_resaas.saas.core.exceptions import ResaasAPIException
from django_resaas.saas.core.services.site_service import entity_for_origin
from saude.serializers.appointment_request import PublicAppointmentRequestSerializer
from saude.services import public_booking_service


class _AddressThrottle(SimpleRateThrottle):
    """Per client address, signed in or not (a public form is abused by address)."""

    setting = None
    default_rate = None

    def get_rate(self):
        return getattr(settings, self.setting, self.default_rate)

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class PublicBookingReadThrottle(_AddressThrottle):
    scope = "saude_public_booking_read"
    setting = "SAUDE_PUBLIC_BOOKING_READ_THROTTLE_RATE"
    default_rate = "300/hour"


class PublicBookingRequestThrottle(_AddressThrottle):
    scope = "saude_public_booking_request"
    setting = "SAUDE_PUBLIC_BOOKING_THROTTLE_RATE"
    default_rate = "10/hour"


@registerView("publicbooking")
class PublicBookingViewSet(viewsets.ViewSet):
    """Online booking of the clinic's public site.

    PUBLIC (explicit): used by visitors who have no session, like the site's
    contact form (django_resaas SiteContactAPIView). The Entity comes from the
    request Origin (entity_for_origin) - never from the query or body - and
    every action is throttled per client address. Visitors only get doctor
    names, specialties, photos and free/booked times; a booking is an
    AppointmentRequest that staff confirm (AppointmentRequestAPIView).

        GET  saude/publicbooking/doctors/
        GET  saude/publicbooking/availability/?doctor=<id>&date=YYYY-MM-DD
        POST saude/publicbooking/requests/
    """

    permission_classes = (permissions.AllowAny,)

    def get_throttles(self):
        if self.action == "requests":
            return [PublicBookingRequestThrottle()]
        return [PublicBookingReadThrottle()]

    @staticmethod
    def _entity(request):
        entity = entity_for_origin(request.headers.get("Origin"))
        if entity is None:
            raise ResaasAPIException(
                "This site is not linked to any organisation.",
                code="site_not_found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return entity

    @action(detail=False, methods=["get"])
    def doctors(self, request):
        return Response(public_booking_service.public_doctors(self._entity(request), request))

    @action(detail=False, methods=["get"])
    def availability(self, request):
        return Response(public_booking_service.available_slots(
            self._entity(request), request.query_params.get("doctor"), request.query_params.get("date")
        ))

    @action(detail=False, methods=["post"])
    def requests(self, request):
        entity = self._entity(request)
        serializer = PublicAppointmentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        # a filled honeypot is a bot: answer like a success, hold no slot
        if data.get("website"):
            return Response({"received": True}, status=status.HTTP_201_CREATED)

        appointment_request = public_booking_service.request_appointment(
            entity, request.headers.get("Origin"), data
        )
        return Response(
            {
                "received": True,
                "date": appointment_request.data.isoformat(),
                "time": appointment_request.hora_inicio.strftime("%H:%M"),
            },
            status=status.HTTP_201_CREATED,
        )
