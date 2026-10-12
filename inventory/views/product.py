from decimal import Decimal, InvalidOperation

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action

from inventory import services
from inventory.models.product import Product
from inventory.serializers.product import ProductSerializer


@registerView("products")
class ProductAPIView(BaseAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    @resaas_action(
        methods=["get"], detail=True, label="Price", icon="sell",
        tooltip="Price of the product for a price list and quantity", position="l", order=10,
    )
    def price(self, request, pk=None):
        """GET ?price_list=<id>&quantity=<n> -> {"price", "price_list"}."""
        product = self.get_object()
        try:
            quantity = Decimal(request.query_params.get("quantity") or "1")
        except InvalidOperation:
            raise ValidationError({"quantity": ["Enter a valid quantity."]})
        return Response(services.get_price(
            product.id, request.entity_id, price_list_id=request.query_params.get("price_list") or None, quantity=quantity,
        ))
