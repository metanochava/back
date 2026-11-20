from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from django_resaas.saas.core.base.permissions import isPermited
from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action
from django_resaas.saas.core.utils import all, fail

from sales.models.payment import Payment
from sales.models.sale import Sale
from sales.serializers.sale import SaleSerializer
from sales.serializers.payment import PaymentSerializer
from sales import services


def _as_drf_validation_error(exc):
    return DRFValidationError(
        exc.messages if hasattr(exc, "messages") else str(exc)
    )


def _validate_warehouse(request, validated):
    """warehouse_id must be one of the Entity's warehouses (needs inventory)."""
    warehouse_id = validated.get("warehouse_id")
    if not warehouse_id:
        return
    inventory_services = services.inventory()
    if not inventory_services or not inventory_services.get_warehouse_snapshot(warehouse_id, request.entity_id):
        raise DRFValidationError({"warehouse_id": ["Does not belong to the current entity."]})


def _tab_data(sale, with_lines=True):
    """An open tab as the point of sale shows it."""
    data = {
        "id": str(sale.id),
        "tab_label": sale.tab_label,
        "estado": sale.estado,
        "customer": str(sale.customer_id) if sale.customer_id else None,
        "customer_label": sale.cliente_label if sale.customer_id else None,
        "warehouse_id": str(sale.warehouse_id) if sale.warehouse_id else None,
        "subtotal": sale.subtotal,
        "desconto_total": sale.desconto_total,
        "tax_total": sale.tax_total,
        "total": sale.total,
        "saldo_devedor": sale.saldo_devedor,
        "created_at": sale.created_at,
        "updated_at": sale.updated_at,
    }
    if with_lines:
        data["lines"] = [
            {
                "id": str(item.id), "product_id": str(item.product_id) if item.product_id else None,
                "product_nome": item.product_nome, "product_codigo": item.product_codigo,
                "quantidade": item.quantidade, "preco_unitario": item.preco_unitario,
                "desconto_valor": item.desconto_valor, "subtotal": item.subtotal,
            }
            for item in sale.itens.order_by("created_at")
        ]
    else:
        data["line_count"] = getattr(sale, "lines", None)
    return data


def _tab_error(request, exc):
    if isinstance(exc, services.TabNotOpen):
        return fail(request, "This tab is no longer open.", status=409, code="tab_not_open")
    raise DRFValidationError(exc.message_dict if hasattr(exc, "error_dict") else exc.messages)


@registerView("sales")
class SaleAPIView(BaseAPIView):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer

    def apply_dynamic_search(self, qs):
        """The receipt number (the first 8 hex digits of the sale's id, printed
        as "RECEIPT 668DEBD8" and as its barcode) finds the sale too: a barcode
        scanner typing it into the search box opens it. Still inside the
        request's tenant scope (qs)."""
        import re

        search = (self.request.query_params.get("search") or "").strip()
        if re.fullmatch(r"[0-9a-fA-F]{8}", search):
            by_number = qs.filter(id__istartswith=search.lower())
            if by_number.exists():
                return by_number
        return super().apply_dynamic_search(qs)

    def perform_create(self, serializer):
        _validate_warehouse(self.request, serializer.validated_data)
        super().perform_create(serializer)

    def perform_update(self, serializer):
        _validate_warehouse(self.request, serializer.validated_data)
        super().perform_update(serializer)

    # ---------------- POINT OF SALE ----------------

    @resaas_action(
        methods=["post"],
        detail=False,
        label="Checkout",
        icon="point_of_sale",
        tooltip="Creates and confirms the point of sale's cart as one sale",
        visible=False,
    )
    def checkout(self, request):
        """POST {checkout_key, lines: [{product_id, quantidade, desconto_valor?}],
        customer?, warehouse_id?, tax?, observacao?} -> 201 the confirmed sale
        (202 - the POST convention for an existing result - the same sale when
        checkout_key was already used). Prices are
        the catalog's for the customer; a discount needs discount_sale."""
        data = request.data
        _validate_warehouse(request, {"warehouse_id": data.get("warehouse_id")})
        try:
            sale, created = services.checkout_sale(
                entity_id=request.entity_id,
                branch_id=request.branch_id,
                user=request.user,
                lines=data.get("lines") if isinstance(data.get("lines"), list) else [],
                checkout_key=data.get("checkout_key"),
                customer_id=data.get("customer") or None,
                warehouse_id=data.get("warehouse_id") or None,
                tax_id=data.get("tax") or None,
                observacao=data.get("observacao") or None,
                can_discount=isPermited(request=request, role="discount_sale"),
            )
        except services.DiscountNotAllowed:
            return fail(request, "You cannot give a discount on a sale.", status=403)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.message_dict if hasattr(exc, "error_dict") else exc.messages)
        return all(request, data=self.get_serializer(sale).data, status=201 if created else 200)

    @resaas_action(
        methods=["get"],
        detail=False,
        label="Quote",
        icon="sell",
        tooltip="Price of a product for a customer before the sale exists",
        visible=False,
        permission="checkout_sale",
    )
    def quote(self, request):
        """GET ?product=<id>&quantidade=<n>&customer=<id?> -> {"price", "price_list"}:
        what checkout will charge for that line."""
        try:
            quantity = Decimal(request.query_params.get("quantidade") or "1")
        except InvalidOperation:
            raise DRFValidationError({"quantidade": ["Enter a valid quantity."]})
        price = services.quote(
            entity_id=request.entity_id,
            product_id=request.query_params.get("product"),
            quantity=quantity,
            customer_id=request.query_params.get("customer") or None,
        )
        if price is None:
            raise DRFValidationError({"product": ["Does not belong to the current entity."]})
        return all(request, data=price)

    @resaas_action(
        methods=["get"],
        detail=False,
        label="Payment methods",
        icon="payments",
        tooltip="The payment methods a sale accepts",
        visible=False,
        permission="checkout_sale",
    )
    def payment_methods(self, request):
        """GET -> [{value, label}]: Payment.FORMA_CHOICES (labels canonical English)."""
        return all(request, data=[{"value": value, "label": label} for value, label in Payment.FORMA_CHOICES])

    # ---------------- OPEN TABS (bar, restaurant) ----------------
    # A tab is a named draft sale; the branch's staff add orders to it from
    # any device until it is closed and paid. Same capability as the point
    # of sale (checkout_sale); a discount needs discount_sale.

    @resaas_action(methods=["get"], detail=False, label="Open tabs", icon="table_bar",
                   tooltip="The branch's open tabs", visible=False, permission="checkout_sale")
    def open_tabs(self, request):
        tabs = services.open_tabs(entity_id=request.entity_id, branch_id=request.branch_id)
        return all(request, data=[_tab_data(tab, with_lines=False) for tab in tabs])

    @resaas_action(methods=["post"], detail=False, label="Open tab", icon="add",
                   tooltip="Opens a tab with a name or a table", visible=False, permission="checkout_sale")
    def open_tab(self, request):
        """POST {tab_label, customer?, warehouse_id?} -> 201 the new tab."""
        _validate_warehouse(request, {"warehouse_id": request.data.get("warehouse_id")})
        try:
            tab = services.open_tab(
                entity_id=request.entity_id, branch_id=request.branch_id, user=request.user,
                label=request.data.get("tab_label"), customer_id=request.data.get("customer") or None,
                warehouse_id=request.data.get("warehouse_id") or None,
            )
        except DjangoValidationError as exc:
            return _tab_error(request, exc)
        return all(request, data=_tab_data(tab), status=201)

    @resaas_action(methods=["get"], detail=True, label="Tab", icon="receipt_long",
                   tooltip="An open tab with its lines", visible=False, permission="checkout_sale")
    def tab(self, request, pk=None):
        return all(request, data=_tab_data(self.get_object()))

    @resaas_action(methods=["post"], detail=True, label="Order", icon="local_bar",
                   tooltip="Adds or takes back units of an item on the tab", visible=False,
                   permission="checkout_sale")
    def order(self, request, pk=None):
        """POST {product_id, delta} (delta 1 by default; negative takes back)."""
        try:
            tab = services.order_on_tab(sale=self.get_object(), product_id=request.data.get("product_id"),
                                        delta=request.data.get("delta", 1), user=request.user)
        except (DjangoValidationError, services.TabNotOpen) as exc:
            return _tab_error(request, exc)
        return all(request, data=_tab_data(tab))

    @resaas_action(methods=["post"], detail=True, label="Discount", icon="percent",
                   tooltip="A line's discount on the tab", visible=False, permission="discount_sale")
    def discount(self, request, pk=None):
        """POST {item, desconto_valor}."""
        try:
            tab = services.discount_on_tab(sale=self.get_object(), item_id=request.data.get("item"),
                                           desconto_valor=request.data.get("desconto_valor"), user=request.user)
        except (DjangoValidationError, services.TabNotOpen) as exc:
            return _tab_error(request, exc)
        return all(request, data=_tab_data(tab))

    @resaas_action(methods=["post"], detail=True, label="Split", icon="call_split",
                   tooltip="Moves some of the tab's items to a new tab", visible=False,
                   permission="checkout_sale")
    def split(self, request, pk=None):
        """POST {items: [{item, quantidade}], tab_label?} -> 201 the new tab."""
        items = request.data.get("items")
        try:
            new_tab = services.split_tab(sale=self.get_object(), items=items if isinstance(items, list) else [],
                                         user=request.user, label=request.data.get("tab_label"))
        except (DjangoValidationError, services.TabNotOpen) as exc:
            return _tab_error(request, exc)
        return all(request, data=_tab_data(new_tab), status=201)

    @resaas_action(methods=["post"], detail=True, label="Close tab", icon="point_of_sale",
                   tooltip="Confirms the tab so it can be paid", visible=False, permission="checkout_sale")
    def close(self, request, pk=None):
        """POST {tax?, warehouse_id?} -> the confirmed sale (a tab already
        closed answers it again instead of confirming twice)."""
        _validate_warehouse(request, {"warehouse_id": request.data.get("warehouse_id")})
        try:
            sale, _closed_now = services.close_tab(sale=self.get_object(), user=request.user,
                                                   tax_id=request.data.get("tax") or None,
                                                   warehouse_id=request.data.get("warehouse_id") or None)
        except (DjangoValidationError, services.TabNotOpen) as exc:
            return _tab_error(request, exc)
        return all(request, data=self.get_serializer(sale).data)

    @resaas_action(
        methods=["get"],
        detail=True,
        label="Disponibilidade",
        icon="inventory",
        tooltip="Verifica stock disponível para as linhas desta venda",
        position="l",
        order=10,
    )
    def disponibilidade(self, request, pk=None):
        sale = self.get_object()
        return all(
            request,
            data=services.check_stock_availability(sale)
        )

    @resaas_action(
        methods=["get"],
        detail=True,
        label="Price",
        icon="sell",
        tooltip="Price of a product for this sale's customer",
        position="l",
        order=12,
    )
    def preco(self, request, pk=None):
        """GET ?product=<id>&quantidade=<n> -> {"price", "price_list"}."""
        sale = self.get_object()
        try:
            quantity = Decimal(request.query_params.get("quantidade") or "1")
        except InvalidOperation:
            raise DRFValidationError({"quantidade": ["Enter a valid quantity."]})
        price = services.price_for(sale, request.query_params.get("product"), quantity)
        if price is None:
            raise DRFValidationError({"product": ["Does not belong to the current entity."]})
        return all(request, data=price)

    @resaas_action(
        methods=["post"],
        detail=True,
        label="Reserve stock",
        icon="lock",
        tooltip="Hold the stock of this draft sale until it is confirmed or cancelled",
        position="t",
        order=15,
        visible=True,
    )
    def reservar(self, request, pk=None):
        sale = self.get_object()

        try:
            reservations = services.reserve_sale_stock(sale=sale, user=request.user)
        except DjangoValidationError as exc:
            raise _as_drf_validation_error(exc)

        return all(
            request,
            data={"reserved": [{"product_id": str(r.product_id), "quantity": r.quantity} for r in reservations]},
        )

    @resaas_action(
        methods=["post"],
        detail=True,
        label="Confirmar",
        icon="check_circle",
        tooltip="Confirma a venda e movimenta o stock (se aplicável)",
        position="t",
        order=20,
        visible=True,
    )
    def confirmar(self, request, pk=None):
        sale = self.get_object()

        try:
            services.confirm_sale(sale=sale, user=request.user)
        except DjangoValidationError as exc:
            raise _as_drf_validation_error(exc)

        return all(
            request,
            data=self.get_serializer(sale).data
        )

    @resaas_action(
        methods=["post"],
        detail=True,
        label="Anular",
        icon="cancel",
        tooltip="Anula a venda e devolve o stock movimentado (se aplicável)",
        position="t",
        order=30,
        visible=True,
    )
    def anular(self, request, pk=None):
        sale = self.get_object()

        try:
            services.cancel_sale(sale=sale, user=request.user)
        except DjangoValidationError as exc:
            raise _as_drf_validation_error(exc)

        return all(
            request,
            data=self.get_serializer(sale).data
        )

    @resaas_action(
        methods=["post"],
        detail=True,
        label="Registar Pagamento",
        icon="payments",
        tooltip="Regista um pagamento parcial ou total desta venda",
        position="t",
        order=40,
        visible=True,
    )
    def pagar(self, request, pk=None):
        sale = self.get_object()

        try:
            payment = services.add_payment(
                sale=sale,
                valor=request.data.get("valor"),
                forma_pagamento=request.data.get("forma_pagamento"),
                referencia=request.data.get("referencia"),
                user=request.user,
            )
        except DjangoValidationError as exc:
            raise _as_drf_validation_error(exc)
        except (TypeError, ValueError):
            raise DRFValidationError("Valor de pagamento inválido.")

        sale.refresh_from_db()

        return all(
            request,
            data={
                "payment": PaymentSerializer(payment).data,
                "sale": self.get_serializer(sale).data,
            }
        )
