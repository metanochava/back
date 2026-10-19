from django_resaas.saas.core.base.views import BaseAPIView, registerView

from farmacia.models.pharmacy_offer import PharmacyOffer
from farmacia.serializers.pharmacy_offer import PharmacyOfferSerializer


@registerView("pharmacyoffers")
class PharmacyOfferAPIView(BaseAPIView):
    queryset = PharmacyOffer.objects.all()
    serializer_class = PharmacyOfferSerializer
