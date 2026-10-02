# hr/views/employee_offboarding.py

from django.db import transaction
from rest_framework.response import Response
from rest_framework import status

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action

from hr.models.employee_offboarding import EmployeeOffboarding
from hr.serializers.employee_offboarding import EmployeeOffboardingSerializer
from hr.services import lifecycle_service


@registerView('employeeoffboardings', module='hr')
class EmployeeOffboardingAPIView(BaseAPIView):
    queryset = EmployeeOffboarding.objects.all()
    serializer_class = EmployeeOffboardingSerializer

    # Creation is exclusively through EmployeeAPIView.start_offboarding -
    # same reasoning EmployeeOnboarding used in Fase 5.
    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use POST /hr/employees/{id}/start_offboarding/ instead."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @resaas_action(detail=True, methods=["post"])
    def complete(self, request, *args, **kwargs):
        offboarding = self.get_object()

        try:
            with transaction.atomic():
                lifecycle_service.complete_offboarding(offboarding, actor=request.user)
        except lifecycle_service.LifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            EmployeeOffboardingSerializer(offboarding, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @resaas_action(detail=True, methods=["post"])
    def cancel(self, request, *args, **kwargs):
        offboarding = self.get_object()

        try:
            with transaction.atomic():
                lifecycle_service.cancel_offboarding(offboarding, actor=request.user)
        except lifecycle_service.LifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            EmployeeOffboardingSerializer(offboarding, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
