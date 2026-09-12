from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action
from django_resaas.saas.core.utils import all

from django_resaas.hr.models.employee import Employee

from farmacia.models.filafarmacia import FilaFarmacia
from farmacia.serializers.filafarmacia import FilaFarmaciaSerializer
from farmacia import services


def _as_drf_validation_error(exc):
    return DRFValidationError(
        exc.messages if hasattr(exc, "messages") else str(exc)
    )


def _get_employee(request, field="employee_id"):
    employee_id = request.data.get(field)

    if not employee_id:
        raise DRFValidationError({field: "Este campo é obrigatório."})

    employee = Employee.objects.filter(id=employee_id).first()

    if not employee:
        raise DRFValidationError({field: "Employee não encontrado."})

    return employee


@registerView("filafarmacias")
class FilaFarmaciaAPIView(BaseAPIView):
    queryset = FilaFarmacia.objects.all()
    serializer_class = FilaFarmaciaSerializer

    @resaas_action(
        methods=["post"],
        detail=True,
        label="Rever",
        icon="fact_check",
        tooltip="Aprova ou rejeita esta prescrição para dispensação",
        position="t",
        order=10,
        visible=True,
    )
    def revisar(self, request, pk=None):
        fila = self.get_object()
        employee = _get_employee(request)

        try:
            services.review(
                fila,
                aprovado=bool(request.data.get("aprovado")),
                motivo_rejeicao=request.data.get("motivo_rejeicao"),
                employee=employee,
                user=request.user,
            )
        except DjangoValidationError as exc:
            raise _as_drf_validation_error(exc)

        return all(request, data=self.get_serializer(fila).data)

    @resaas_action(
        methods=["post"],
        detail=True,
        label="Dispensar",
        icon="medication",
        tooltip="Regista a dispensação dos itens desta prescrição",
        position="t",
        order=20,
        visible=True,
    )
    def dispensar(self, request, pk=None):
        fila = self.get_object()
        employee = _get_employee(request)

        try:
            dispensa = services.dispense(
                fila,
                itens=request.data.get("itens") or [],
                warehouse_id=request.data.get("warehouse_id"),
                employee=employee,
                user=request.user,
            )
        except DjangoValidationError as exc:
            raise _as_drf_validation_error(exc)

        from farmacia.serializers.dispensa import DispensaSerializer

        return all(
            request,
            data={
                "dispensa": DispensaSerializer(dispensa).data,
                "fila": self.get_serializer(fila).data,
            }
        )

    @resaas_action(
        methods=["post"],
        detail=True,
        label="Concluir",
        icon="task_alt",
        tooltip="Marca esta prescrição como totalmente dispensada",
        position="t",
        order=30,
        visible=True,
    )
    def concluir(self, request, pk=None):
        fila = self.get_object()

        try:
            services.concluir(fila, user=request.user)
        except DjangoValidationError as exc:
            raise _as_drf_validation_error(exc)

        return all(request, data=self.get_serializer(fila).data)
