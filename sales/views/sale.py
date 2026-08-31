from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from django_resaas.core.base.views import BaseAPIView, registerView
from django_resaas.core.decorators import resaas_action
from django_resaas.core.utils import all

from sales.models.sale import Sale
from sales.serializers.sale import SaleSerializer
from sales.serializers.payment import PaymentSerializer
from sales import services


def _as_drf_validation_error(exc):
    return DRFValidationError(
        exc.messages if hasattr(exc, "messages") else str(exc)
    )


@registerView("sales")
class SaleAPIView(BaseAPIView):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer

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
