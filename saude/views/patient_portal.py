"""Patient portal - GET /api/saude/me/<section>/ (read only).

PROTECTED. Two barriers, both required on every request:

    authentication
      -> signed tenant context, re-validated for this user
      -> saude module active for the Entity
      -> PERMISSION of the section in the active profile (the "Patient"
         profile has them: view_patient_portal, view_own_*) - ActionPermissionMixin
      -> OWNERSHIP: the user's own Paciente of that Entity with portal_access
      -> data of that patient only (saude/services/patient_portal_service.py)

The permission says the profile may USE a section; it never widens what is
returned - every query starts from the caller's own Paciente.

No endpoint takes a patient id: the patient is never chosen by the client.
`status` always answers 200 (portal available or not) so a staff member
landing on the welcome page gets no error.
"""
from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from django_resaas.saas.core.base.access import ActionPermissionMixin, ExplicitAccessMixin
from django_resaas.saas.core.base.permissions import isPermited
from django_resaas.saas.core.base.dashboard import is_module_active
from django_resaas.saas.core.base.views import registerView
from django_resaas.saas.core.exceptions import ResaasAPIException
from django_resaas.saas.core.tenant.context import ResaasContextService

from saude.services import patient_portal_service as portal


@registerView("me")
class PatientPortalViewSet(ActionPermissionMixin, ExplicitAccessMixin, viewsets.ViewSet):
    # PROTECTED: authenticated + tenant context + section permission + ownership

    # status needs no permission (always 200, it SAYS whether the portal is
    # available); every section needs its own
    membership_actions = ("status",)
    action_permissions = {
        "summary": "view_patient_portal",
        "appointments": "view_own_appointments",
        "exams": "view_own_exams",
        "results": "view_own_results",
        "trends": "view_own_trends",
        "prescriptions": "view_own_prescriptions",
        "vitals": "view_own_vitals",
    }

    def initial(self, request, *args, **kwargs):
        self._check_context(request)
        super().initial(request, *args, **kwargs)

    def _check_context(self, request):
        error = getattr(request, "tenant_context_error", None)
        if error:
            raise error if isinstance(error, PermissionDenied) else PermissionDenied(str(error))

        if not getattr(request, "tenant_context", None) or not getattr(request, "entity_id", None):
            raise PermissionDenied("RESAAS context is required.")

        ResaasContextService.validate_for_user(request.user, request.tenant_context)

        # status answers {"portal": false} instead (see status())
        if self.action != "status" and not is_module_active(request.entity_id, "saude"):
            raise ResaasAPIException("Module not active", code="module_not_active", status_code=403)

    # ---------------------------------------------------------------

    @action(detail=False, methods=["get"])
    def status(self, request):
        if not is_module_active(request.entity_id, "saude"):
            return Response({"portal": False, "patient": None})

        paciente = portal.resolve_self(request)
        if paciente is not None and not isPermited(request=request, role="view_patient_portal"):
            paciente = None  # the active profile can't use the portal
        return Response({
            "portal": paciente is not None,
            "patient": paciente.person.full_name if paciente else None,
        })

    @action(detail=False, methods=["get"])
    def summary(self, request):
        return Response(portal.summary(portal.require_self(request)))

    @action(detail=False, methods=["get"])
    def appointments(self, request):
        return Response(portal.appointments(portal.require_self(request)))

    @action(detail=False, methods=["get"])
    def exams(self, request):
        return Response(portal.exams(portal.require_self(request)))

    @action(detail=False, methods=["get"])
    def results(self, request):
        return Response(portal.results(portal.require_self(request)))

    @action(detail=False, methods=["get"])
    def prescriptions(self, request):
        return Response(portal.prescriptions(portal.require_self(request)))

    @action(detail=False, methods=["get"])
    def vitals(self, request):
        return Response(portal.vitals(portal.require_self(request)))

    @action(detail=False, methods=["get"])
    def trends(self, request):
        """Without ?parameter: the patient's chartable parameters. With
        ?parameter=<code>&from=&to=: its released, patient-visible series."""
        paciente = portal.require_self(request)
        code = request.query_params.get("parameter")

        if not code:
            return Response(portal.trend_parameters(paciente))

        try:
            date_from = parse_date(request.query_params.get("from") or "")
            date_to = parse_date(request.query_params.get("to") or "")
        except ValueError:
            raise ResaasAPIException("Invalid date.", code="invalid_date")

        return Response(portal.trend(paciente, code, date_from, date_to))
