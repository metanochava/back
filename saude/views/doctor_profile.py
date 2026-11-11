"""The doctor dialog of the app - GET saude/doctorprofile/<employee id>/[?scope=entity|global].

PROTECTED (membership): any member of the Entity, in a valid signed context,
with the saude module active. No HR or doctor permission: it returns only what
the clinic's public site already shows of a doctor (public_doctor_row) and the
rating; whoever may moderate comments (moderate_employeerating) also gets the
pending ones. The employee must belong to the context Entity (any of its
branches - the doctor of a record may work in another one).
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from django_resaas.saas.core.base.access import ActionPermissionMixin, ExplicitAccessMixin
from django_resaas.saas.core.base.dashboard import is_module_active
from django_resaas.saas.core.base.permissions import isPermited
from django_resaas.saas.core.base.views import registerView
from django_resaas.saas.core.exceptions import ResaasAPIException
from django_resaas.saas.core.tenant.context import ResaasContextService

from django_resaas.saas.models.branch import Branch
from hr.models.employee import Employee
from hr.services import employee_rating_service
from saude.services.public_booking_service import public_doctor_row

MODERATE_PERMISSION = "moderate_employeerating"


@registerView("doctorprofile")
class DoctorProfileViewSet(ActionPermissionMixin, ExplicitAccessMixin, viewsets.ViewSet):
    # PROTECTED: authenticated + tenant context + module active; scope = own Entity
    membership_actions = ("retrieve",)

    def initial(self, request, *args, **kwargs):
        error = getattr(request, "tenant_context_error", None)
        if error:
            raise error if isinstance(error, PermissionDenied) else PermissionDenied(str(error))
        super().initial(request, *args, **kwargs)
        if not getattr(request, "tenant_context", None) or not getattr(request, "entity_id", None):
            raise PermissionDenied("RESAAS context is required.")
        ResaasContextService.validate_for_user(request.user, request.tenant_context)
        if not is_module_active(request.entity_id, "saude"):
            raise ResaasAPIException("Module not active", code="module_not_active", status_code=403)

    def retrieve(self, request, pk=None):
        try:
            employee = (
                Employee.objects.select_related("person", "medico")
                .filter(id=pk, entity_id=request.entity_id).first()
            )
        except (DjangoValidationError, ValueError):
            employee = None
        if employee is None:
            raise ResaasAPIException("Doctor not found.", code="doctor_not_found", status_code=404)

        can_moderate = bool(isPermited(request=request, role=MODERATE_PERMISSION))
        scope = employee_rating_service.parse_scope(request.query_params.get("scope"))
        medico = getattr(employee, "medico", None)
        data = public_doctor_row(employee, request)
        data.update({
            "rating": employee_rating_service.summary(employee, scope, pending=can_moderate),
            "medico_id": str(medico.id) if medico is not None else None,
            "active": medico.ativo if medico is not None else True,
            "can_moderate": can_moderate,
            "branch_names": list(
                Branch.objects.filter(id__in=data["branches"], entity_id=request.entity_id)
                .order_by("name").values_list("name", flat=True)
            ),
        })
        return Response(data)
