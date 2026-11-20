from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from django_resaas.saas.core.base.views import registerView
from saude.services import public_site_service
from saude.views.public_booking_read_throttle import PublicBookingReadThrottle
from saude.views.public_booking import PublicBookingViewSet


@registerView("publicsite")
class PublicSiteViewSet(viewsets.ViewSet):
    """What the clinic's public site reads.

    PUBLIC (explicit): read by visitors who have no session. The Entity comes
    from the request Origin (like publicbooking/), never from the client;
    throttled per client address; read-only (GET never writes).

        GET saude/publicsite/stats/                    aggregate counts
        GET saude/publicsite/exams/                    active exams + price
        GET saude/publicsite/exams/<id>/               one exam (404 if not this clinic's)
        GET saude/publicsite/consultations/            price per specialty
        GET saude/publicsite/consultations/<key>/      one (specialty id or "general") + its doctors
    """

    permission_classes = (permissions.AllowAny,)
    throttle_classes = (PublicBookingReadThrottle,)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        entity = PublicBookingViewSet._entity(request)
        return Response(public_site_service.stats(entity))

    @action(detail=False, methods=["get"])
    def exams(self, request):
        return Response(public_site_service.exams(PublicBookingViewSet._entity(request)))

    @action(detail=False, methods=["get"], url_path=r"exams/(?P<exam_id>[^/.]+)")
    def exam(self, request, exam_id=None):
        return Response(public_site_service.exam(PublicBookingViewSet._entity(request), exam_id, request))

    @action(detail=False, methods=["get"])
    def consultations(self, request):
        return Response(public_site_service.consultations(PublicBookingViewSet._entity(request)))

    @action(detail=False, methods=["get"], url_path=r"consultations/(?P<key>[^/.]+)")
    def consultation(self, request, key=None):
        return Response(public_site_service.consultation(PublicBookingViewSet._entity(request), key, request))
