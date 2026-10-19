import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.throttling import SimpleRateThrottle

from django_resaas.saas.core.base.access import ExplicitAccessMixin
from django_resaas.saas.core.base.views import registerView
from django_resaas.saas.core.exceptions import ResaasAPIException
from django_resaas.saas.core.utils.pagination import ResaasPagination

from rest_framework import serializers
from rest_framework.response import Response

from farmacia import marketplace_service, online_order_service
from farmacia.models import OnlineOrder
from farmacia.serializers.online_order import effective_status


class MarketplaceThrottle(SimpleRateThrottle):
    """Per client address, signed in or not: FARMACIA_MARKETPLACE_THROTTLE_RATE,
    default 600/hour."""

    scope = "farmacia_marketplace"

    def get_rate(self):
        return getattr(settings, "FARMACIA_MARKETPLACE_THROTTLE_RATE", "600/hour")

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class MarketplacePagination(ResaasPagination):
    page_size = 20
    max_page_size = 50

    def paginate_queryset(self, queryset, request, view=None):
        # never everything at once (ResaasPagination's page_size=0)
        if request.query_params.get(self.page_size_query_param) == "0":
            raise ValidationError({"page_size": ["Must be between 1 and 50."]})
        return super().paginate_queryset(queryset, request, view)


def _origin(params):
    """{"lat","lng"} from ?lat=&lng=, None when absent; 400 when malformed."""
    lat, lng = params.get("lat"), params.get("lng")
    if lat in (None, "") and lng in (None, ""):
        return None
    try:
        origin = {"lat": float(lat), "lng": float(lng)}
    except (TypeError, ValueError):
        raise ValidationError({"lat": ["Latitude and longitude must both be numbers."]})
    if not (-90 <= origin["lat"] <= 90 and -180 <= origin["lng"] <= 180):
        raise ValidationError({"lat": ["Latitude and longitude are out of range."]})
    return origin


def _uuid(params, name):
    value = params.get(name)
    if value in (None, ""):
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise ValidationError({name: ["Not a valid identifier."]})


def _price(params, name):
    value = params.get(name)
    if value in (None, ""):
        return None
    try:
        price = Decimal(value)
    except InvalidOperation:
        raise ValidationError({name: ["A valid number is required."]})
    if price < 0:
        raise ValidationError({name: ["Must not be negative."]})
    return price


class OrderLine(serializers.Serializer):
    offer_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=16, decimal_places=3)


class PlaceOrderInput(serializers.Serializer):
    lines = OrderLine(many=True)
    contact_name = serializers.CharField(max_length=150)
    contact_phone = serializers.CharField(max_length=40)
    idempotency_key = serializers.CharField(max_length=64)


def buyer_order(order, pharmacy):
    """What the buyer sees of their order: never the warehouse, the sale or
    who handled it at the pharmacy."""
    return {
        "id": str(order.id),
        "reference": order.reference,
        "status": effective_status(order),
        "pharmacy": pharmacy,
        "items": [
            {"medicine": item.medicine_name, "quantity": str(item.quantity.normalize()),
             "unit_price": str(item.unit_price), "prescription_required": item.prescription_required}
            for item in order.items.all()
        ],
        "total": str(order.total),
        "currency": order.currency,
        "prescription_required": order.prescription_required,
        "expires_at": order.expires_at.isoformat(),
        "created_at": order.created_at.isoformat(),
        "collected_at": order.collected_at.isoformat() if order.collected_at else None,
        "cancelled_at": order.cancelled_at.isoformat() if order.cancelled_at else None,
    }


def _buyer_orders(request):
    return OnlineOrder.objects.filter(buyer=request.user).prefetch_related("items")


def _with_pharmacies(orders):
    listings = {listing.branch_id: listing for listing in marketplace_service.listings_of(
        {order.branch_id for order in orders})}
    return [buyer_order(order, marketplace_service.pharmacy_card(listings.get(order.branch_id), order))
            for order in orders]


@registerView("marketplace")
class MarketplaceViewSet(ExplicitAccessMixin, viewsets.ViewSet):
    """
    The pharmacies' marketplace (farmacia/marketplace_service.py).

        GET farmacia/marketplace/pharmacies/  PUBLIC  published pharmacies
            ?lat=&lng=  by distance (only from real coordinates)
            ?q=&country=&city=&neighborhood=&id=  manual search
        GET farmacia/marketplace/medicines/   PROTECTED (signed in)  offers
            ?q=  name, substance, brand, strength, form, presentation, code
            ?medicine=&pharmacy=&dosage_form=&strength=
            ?min_price=&max_price=&available=1&sort=price|distance&lat=&lng=
        GET  farmacia/marketplace/orders/              PROTECTED  the caller's orders
        POST farmacia/marketplace/orders/              PROTECTED  reserve: one order per pharmacy
            {lines: [{offer_id, quantity}], contact_name, contact_phone, idempotency_key}
        POST farmacia/marketplace/orders/{id}/cancel/  PROTECTED  only the caller's own order

    Neither needs a tenant context: the search spans every eligible pharmacy,
    whatever Entity the caller works in, and returns only their public
    commercial data. Throttled per client address.
    """

    public_actions = ("pharmacies",)
    throttle_classes = (MarketplaceThrottle,)
    pagination_class = MarketplacePagination

    def _page(self, request, rows, photos=False):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(rows, request, view=self)
        if photos:
            page = marketplace_service.photo_urls(request, page)
        return paginator.get_paginated_response(page)

    @action(detail=False, methods=["get"])
    def pharmacies(self, request):
        params = request.query_params
        rows = marketplace_service.pharmacies(
            origin=_origin(params),
            q=params.get("q"),
            country=params.get("country"),
            city=params.get("city"),
            neighborhood=params.get("neighborhood"),
            listing_id=_uuid(params, "id"),
        )
        return self._page(request, rows)

    @action(detail=False, methods=["get"])
    def medicines(self, request):
        params = request.query_params
        sort = params.get("sort") or marketplace_service.SORT_PRICE
        if sort not in marketplace_service.SORTS:
            raise ValidationError({"sort": ["Must be price or distance."]})
        origin = _origin(params)
        if sort == marketplace_service.SORT_DISTANCE and not origin:
            raise ValidationError({"sort": ["Sorting by distance needs lat and lng."]})
        if not any(params.get(name) for name in ("q", "medicine", "pharmacy")):
            raise ValidationError({"q": ["Type a medicine, or choose a medicine or a pharmacy."]})
        try:
            rows = marketplace_service.search_offers(
                q=params.get("q"),
                catalog_item_id=_uuid(params, "medicine"),
                listing_id=_uuid(params, "pharmacy"),
                dosage_form=params.get("dosage_form"),
                strength=params.get("strength"),
                origin=origin,
                min_price=_price(params, "min_price"),
                max_price=_price(params, "max_price"),
                available_only=params.get("available") in ("1", "true"),
                sort=sort,
            )
        except marketplace_service.SearchTooBroad:
            raise ResaasAPIException(
                "Too many results: add more words or choose a pharmacy.",
                code="search_too_broad",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return self._page(request, rows, photos=True)

    @action(detail=False, methods=["get", "post"])
    def orders(self, request):
        if request.method == "GET":
            return self._page(request, _with_pharmacies(list(_buyer_orders(request))))
        data = PlaceOrderInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        orders = online_order_service.place_orders(
            buyer=request.user,
            lines=[{"offer_id": str(line["offer_id"]), "quantity": line["quantity"]} for line in values["lines"]],
            contact_name=values["contact_name"], contact_phone=values["contact_phone"],
            idempotency_key=values["idempotency_key"],
        )
        orders = list(_buyer_orders(request).filter(id__in=[order.id for order in orders]))
        return Response({"results": _with_pharmacies(orders)}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path=r"orders/(?P<order_id>[0-9a-fA-F-]{36})/cancel")
    def cancel_order(self, request, order_id=None):
        # the caller's own order only: another buyer's id is simply not found
        order = _buyer_orders(request).filter(id=order_id).first()
        if order is None:
            raise ResaasAPIException("Order not found.", code="order_not_found", status_code=status.HTTP_404_NOT_FOUND)
        order = online_order_service.cancel_order(order, user=request.user, reason="Cancelled by the buyer")
        return Response(_with_pharmacies([order])[0])
