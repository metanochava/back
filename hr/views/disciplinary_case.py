# hr/views/disciplinary_case.py

from django.db import transaction
from rest_framework.response import Response
from rest_framework import status

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action

from hr.models.disciplinary_case import DisciplinaryCase
from hr.serializers.disciplinary_case import DisciplinaryCaseSerializer
from hr.services import lifecycle_service


@registerView('disciplinarycases', module='hr')
class DisciplinaryCaseAPIView(BaseAPIView):
    """Sensitive (pedido secção 41) - access is gated by its own dedicated
    view/add/change/delete_disciplinarycase permissions (never assumed
    from view/change_employee), and this data is never surfaced through
    EmployeeSerializer or any other endpoint (pedido secção 58)."""

    queryset = DisciplinaryCase.objects.all()
    serializer_class = DisciplinaryCaseSerializer

    def perform_create(self, serializer):
        super().perform_create(serializer)
        lifecycle_service.case_opened(serializer.instance, actor=self.request.user)

    @resaas_action(detail=True, methods=["post"])
    def start_review(self, request, *args, **kwargs):
        case = self.get_object()

        try:
            with transaction.atomic():
                lifecycle_service.start_review(case, actor=request.user)
        except lifecycle_service.LifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            DisciplinaryCaseSerializer(case, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @resaas_action(detail=True, methods=["post"])
    def resolve(self, request, *args, **kwargs):
        case = self.get_object()

        try:
            with transaction.atomic():
                lifecycle_service.resolve_case(case, actor=request.user)
        except lifecycle_service.LifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            DisciplinaryCaseSerializer(case, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @resaas_action(detail=True, methods=["post"])
    def dismiss(self, request, *args, **kwargs):
        case = self.get_object()

        try:
            with transaction.atomic():
                lifecycle_service.dismiss_case(case, actor=request.user)
        except lifecycle_service.LifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            DisciplinaryCaseSerializer(case, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
