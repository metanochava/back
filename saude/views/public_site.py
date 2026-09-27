from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from django_resaas.saas.core.base.views import registerView
from saude.services import public_site_service
from saude.views.public_booking import PublicBookingReadThrottle, PublicBookingViewSet


@registerView("publicsite")
class PublicSiteViewSet(viewsets.ViewSet):
    """Public figures of the clinic's site.

    PUBLIC (explicit): read by visitors who have no session. The Entity comes
    from the request Origin (like publicbooking/), throttled per client
    address; only aggregate counts are returned.

        GET saude/publicsite/stats/
    """

    permission_classes = (permissions.AllowAny,)
    throttle_classes = (PublicBookingReadThrottle,)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        entity = PublicBookingViewSet._entity(request)
        return Response(public_site_service.stats(entity))
