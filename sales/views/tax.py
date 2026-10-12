from django_resaas.saas.core.base.views import BaseAPIView, registerView

from sales.models.tax import Tax
from sales.serializers.tax import TaxSerializer


@registerView("taxes")
class TaxAPIView(BaseAPIView):
    """A tax already used by a sale line cannot be deleted (PROTECT): set it
    inactive instead - past lines keep their own copied rate."""

    queryset = Tax.objects.all()
    serializer_class = TaxSerializer

    def perform_destroy(self, instance):
        if instance.sale_items.exists():
            from django_resaas.saas.core.exceptions import ConflictError

            raise ConflictError("A tax used in sales cannot be deleted; make it inactive.", code="tax_in_use")
        super().perform_destroy(instance)
