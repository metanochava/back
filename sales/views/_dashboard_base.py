from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied

from django_resaas.core.base.permissions import isPermited
from django_resaas.core.utils.api_response import fail
from django_resaas.models.entity_app import EntityApp


class TenantDashboardAPIView(APIView):
    """
    Base para endpoints de agregação (dashboard) do sales. Duplica de
    propósito a base equivalente do inventory (inventory/views/
    _dashboard_base.py) em vez de importar de lá — os dois módulos não
    trocam código de infraestrutura entre si, só inventory.services
    quando sales precisa mesmo de falar com o inventory.

    REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES está vazio neste
    projeto — sem esta validação manual estes endpoints ficariam
    completamente abertos.
    """

    module_name = None
    permission_codename = None

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)

        if getattr(request, "tenant_context_error", None):
            raise PermissionDenied(str(request.tenant_context_error))

        if not getattr(request, "tenant_context", None):
            raise PermissionDenied("RESAAS context is required.")

        if not request.entity_id:
            return fail(request, "You are not associated with any entity.", status=403)

        if not self.module_name:
            return fail(request, "Module is not defined.", status=403)

        ativo = EntityApp.objects.filter(
            entity_id=request.entity_id,
            app__name=self.module_name,
            state="Active"
        ).exists()

        if not ativo:
            return fail(request, f"Module '{self.module_name}' is not active.", status=403)

        if not self.permission_codename:
            return fail(request, "Permission is not defined for this action.", status=403)

        if not isPermited(request=request, role=self.permission_codename):
            return fail(request, "Unauthorized", status=403)

    def apply_scope(self, request, qs):
        scope = request.query_params.get("scope", "branch")

        if scope == "entity":
            consolidated_codename = f"view_consolidated_dashboard_{self.module_name}"

            if not isPermited(request=request, role=consolidated_codename):
                fail(
                    request,
                    "Sem permissão para consolidado da entity.",
                    status=403
                )

            return qs.filter(entity_id=request.entity_id)

        return qs.filter(
            entity_id=request.entity_id,
            branch_id=request.branch_id
        )

    def require_period(self, request):
        data_inicio = request.query_params.get("data_inicio")
        data_fim = request.query_params.get("data_fim")

        if not data_inicio or not data_fim:
            fail(
                request,
                "data_inicio e data_fim são obrigatórios.",
                status=400
            )

        return data_inicio, data_fim
