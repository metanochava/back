# hr/views/performance_cycle.py

from django.db import transaction
from rest_framework.response import Response
from rest_framework import status

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action

from hr.models.performance_cycle import PerformanceCycle
from hr.serializers.performance_cycle import PerformanceCycleSerializer
from hr.services import performance_service


@registerView('performancecycles', module='hr')
class PerformanceCycleAPIView(BaseAPIView):
    queryset = PerformanceCycle.objects.all()
    serializer_class = PerformanceCycleSerializer

    @resaas_action(detail=True, methods=["post"])
    def close_cycle(self, request, *args, **kwargs):
        cycle = self.get_object()

        try:
            with transaction.atomic():
                performance_service.close_cycle(cycle, actor=request.user)
        except performance_service.PerformanceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            PerformanceCycleSerializer(cycle, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
