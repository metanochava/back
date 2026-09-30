# hr/views/employee_onboarding.py

from django.db import transaction
from rest_framework.response import Response
from rest_framework import status

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action

from hr.models.employee_onboarding import EmployeeOnboarding
from hr.serializers.employee_onboarding import EmployeeOnboardingSerializer
from hr.services import onboarding_service


@registerView('employeeonboardings', module='hr')
class EmployeeOnboardingAPIView(BaseAPIView):
    queryset = EmployeeOnboarding.objects.all()
    serializer_class = EmployeeOnboardingSerializer

    # Creation is exclusively through EmployeeAPIView.start_onboarding()
    # (it needs to copy the template's tasks in the same transaction - see
    # onboarding_service.start_onboarding) - a free POST here would create
    # a row with no tasks and skip that copy, so it's blocked outright
    # rather than left as a confusing half-working path.
    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use POST /hr/employees/{id}/start_onboarding/ instead."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    # get_object() already scopes to the caller's tenant.

    @resaas_action(detail=True, methods=["post"])
    def complete(self, request, *args, **kwargs):
        onboarding = self.get_object()

        try:
            with transaction.atomic():
                onboarding_service.complete_onboarding(onboarding, actor=request.user)
        except onboarding_service.OnboardingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            EmployeeOnboardingSerializer(onboarding, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @resaas_action(detail=True, methods=["post"])
    def cancel(self, request, *args, **kwargs):
        onboarding = self.get_object()

        try:
            with transaction.atomic():
                onboarding_service.cancel_onboarding(onboarding, actor=request.user)
        except onboarding_service.OnboardingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            EmployeeOnboardingSerializer(onboarding, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
