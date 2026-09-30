# hr/views/payroll_period.py

from django.db import transaction
from rest_framework.response import Response
from rest_framework import status

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action

from hr.models.payroll_period import PayrollPeriod
from hr.serializers.payroll_period import PayrollPeriodSerializer
from hr.serializers.payroll import PayrollSerializer
from hr.services import payroll_service


@registerView('payrollperiods', module='hr')
class PayrollPeriodAPIView(BaseAPIView):
    queryset = PayrollPeriod.objects.all()
    serializer_class = PayrollPeriodSerializer

    @resaas_action(detail=True, methods=["post"])
    def generate(self, request, *args, **kwargs):
        """Period -> Generate step (pedido secção 78): creates/recalculates
        one Payroll per active employee of this period's entity/branch.
        Idempotent - see payroll_service.generate_payroll_for_period."""
        period = self.get_object()

        with transaction.atomic():
            payrolls = payroll_service.generate_payroll_for_period(
                period, actor=request.user
            )

        return Response(
            PayrollSerializer(payrolls, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
