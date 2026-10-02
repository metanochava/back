# hr/views/employee_training.py

from django.db import transaction
from rest_framework.response import Response
from rest_framework import status

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action

from hr.models.employee_training import EmployeeTraining
from hr.serializers.employee_training import EmployeeTrainingSerializer
from hr.services import training_service


@registerView('employeetrainings', module='hr')
class EmployeeTrainingAPIView(BaseAPIView):
    queryset = EmployeeTraining.objects.all()
    serializer_class = EmployeeTrainingSerializer

    # Creation is exclusively through TrainingSessionAPIView.enroll() (it
    # needs to check capacity/duplicate-enrollment in the same transaction -
    # see training_service.enroll) - a free POST here would skip both, same
    # reasoning EmployeeOnboarding uses (hr/views/employee_onboarding.py,
    # Fase 5).
    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use POST /hr/trainingsessions/{id}/enroll/ instead."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    # get_object() already scopes to the caller's tenant.

    @resaas_action(detail=True, methods=["post"])
    def mark_completed(self, request, *args, **kwargs):
        enrollment = self.get_object()

        score = request.data.get("score")
        result = request.data.get("result", "")

        try:
            with transaction.atomic():
                training_service.mark_completed(
                    enrollment, actor=request.user, score=score, result=result,
                )
        except training_service.TrainingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            EmployeeTrainingSerializer(enrollment, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @resaas_action(detail=True, methods=["post"])
    def mark_failed(self, request, *args, **kwargs):
        enrollment = self.get_object()

        result = request.data.get("result", "")

        try:
            with transaction.atomic():
                training_service.mark_failed(enrollment, actor=request.user, result=result)
        except training_service.TrainingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            EmployeeTrainingSerializer(enrollment, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
