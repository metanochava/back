from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action
from django_resaas.saas.core.exceptions import ConflictError

from accounting import services
from accounting.models import FiscalPeriod
from accounting.serializers import FiscalPeriodSerializer


@registerView("fiscalperiods")
class FiscalPeriodAPIView(BaseAPIView):
    queryset = FiscalPeriod.objects.all()
    serializer_class = FiscalPeriodSerializer

    def perform_create(self, serializer):
        data = serializer.validated_data
        services.validate_period_dates(self.request.entity_id, data["start_date"], data["end_date"])
        super().perform_create(serializer)

    def perform_update(self, serializer):
        period = serializer.instance
        if period.status == FiscalPeriod.STATUS_CLOSED:
            raise ConflictError("The fiscal period of this date is closed.", code="fiscal_period_closed")
        data = serializer.validated_data
        services.validate_period_dates(
            self.request.entity_id,
            data.get("start_date", period.start_date),
            data.get("end_date", period.end_date),
            exclude_pk=period.pk,
        )
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        if instance.status == FiscalPeriod.STATUS_CLOSED:
            raise ConflictError("The fiscal period of this date is closed.", code="fiscal_period_closed")
        super().perform_destroy(instance)

    @resaas_action(
        methods=["post"], detail=True, label="Close period", icon="lock",
        tooltip="Close the period: no more postings on its dates", position="t", order=10, autorequest=True,
    )
    def close(self, request, pk=None):
        period = services.close_period(period=self.get_object(), user=request.user)
        return Response(self.get_serializer(period).data)

    @resaas_action(
        methods=["post"], detail=True, label="Reopen period", icon="lock_open",
        tooltip="Reopen a closed period", position="t", order=20, autorequest=True,
    )
    def reopen(self, request, pk=None):
        period = services.reopen_period(period=self.get_object(), user=request.user)
        return Response(self.get_serializer(period).data)
