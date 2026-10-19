from django_resaas.saas.core.base.views import BaseAPIView, registerView

from farmacia.models.pharmacy_listing import PharmacyListing
from farmacia.serializers.pharmacy_listing import PharmacyListingSerializer


@registerView("pharmacylistings")
class PharmacyListingAPIView(BaseAPIView):
    queryset = PharmacyListing.objects.all()
    serializer_class = PharmacyListingSerializer
