# hr/views/resignation.py

from django.db import transaction
from rest_framework.response import Response
from rest_framework import status

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action

from hr.models.resignation import Resignation
from hr.serializers.resignation import ResignationSerializer
from hr.services import lifecycle_service


@registerView('resignations', module='hr')
class ResignationAPIView(BaseAPIView):
    queryset = Resignation.objects.all()
    serializer_class = ResignationSerializer

    @resaas_action(detail=True, methods=["post"])
    def accept(self, request, *args, **kwargs):
        resignation = self.get_object()

        try:
            with transaction.atomic():
                lifecycle_service.accept_resignation(resignation, actor=request.user)
        except lifecycle_service.LifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            ResignationSerializer(resignation, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @resaas_action(detail=True, methods=["post"])
    def withdraw(self, request, *args, **kwargs):
        resignation = self.get_object()

        try:
            with transaction.atomic():
                lifecycle_service.withdraw_resignation(resignation, actor=request.user)
        except lifecycle_service.LifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            ResignationSerializer(resignation, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
