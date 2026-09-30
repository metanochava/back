# hr/views/promotion.py

from rest_framework.response import Response
from rest_framework import status

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.promotion import Promotion
from hr.serializers.promotion import PromotionSerializer


@registerView('promotions', module='hr')
class PromotionAPIView(BaseAPIView):
    queryset = Promotion.objects.all()
    serializer_class = PromotionSerializer

    # Creation is exclusively through EmployeeAPIView.apply_promotion (it
    # needs to also update Employee.position/job_grade in the same
    # transaction - see lifecycle_service.apply_promotion), same reasoning
    # EmployeeOnboarding used in Fase 5.
    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use POST /hr/employees/{id}/apply_promotion/ instead."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )
