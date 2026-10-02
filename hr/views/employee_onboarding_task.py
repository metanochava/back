# hr/views/employee_onboarding_task.py

from django.db import transaction
from rest_framework.response import Response
from rest_framework import status

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action

from hr.models.employee_onboarding_task import EmployeeOnboardingTask
from hr.serializers.employee_onboarding_task import (
    EmployeeOnboardingTaskSerializer,
)
from hr.services import onboarding_service


@registerView('employeeonboardingtasks', module='hr')
class EmployeeOnboardingTaskAPIView(BaseAPIView):
    queryset = EmployeeOnboardingTask.objects.all()
    serializer_class = EmployeeOnboardingTaskSerializer

    # get_object() already scopes to the caller's tenant (get_queryset()
    # filters by entity_id/branch_id - see BaseAPIView), same guarantee
    # every other Fase 2/3/4 action relies on.

    @resaas_action(detail=True, methods=["post"])
    def complete(self, request, *args, **kwargs):
        task = self.get_object()
        notes = request.data.get("notes") or ""

        try:
            with transaction.atomic():
                onboarding_service.complete_task(task, actor=request.user, notes=notes)
        except onboarding_service.OnboardingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            EmployeeOnboardingTaskSerializer(task, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @resaas_action(detail=True, methods=["post"])
    def reopen(self, request, *args, **kwargs):
        task = self.get_object()

        try:
            with transaction.atomic():
                onboarding_service.reopen_task(task, actor=request.user)
        except onboarding_service.OnboardingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            EmployeeOnboardingTaskSerializer(task, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
