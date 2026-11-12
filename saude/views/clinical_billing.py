"""Clinical billing and material rules (who keeps them: the clinic's
administration - Health Administrator), and the read-only records of what
was charged / consumed per act. PROTECTED (BaseAPIView, per action)."""
from django_resaas.saas.core.base.views import BaseAPIView, registerView

from saude.models.clinical_billing import ClinicalBillingRule, ClinicalCharge, ExamMaterialRule, MaterialConsumption
from saude.serializers.clinical_billing import (
    ClinicalBillingRuleSerializer, ClinicalChargeSerializer, ExamMaterialRuleSerializer, MaterialConsumptionSerializer,
)


@registerView("clinicalbillingrules")
class ClinicalBillingRuleAPIView(BaseAPIView):
    queryset = ClinicalBillingRule.objects.select_related("specialty", "exame", "medicamento")
    serializer_class = ClinicalBillingRuleSerializer


@registerView("exammaterialrules")
class ExamMaterialRuleAPIView(BaseAPIView):
    queryset = ExamMaterialRule.objects.select_related("exame")
    serializer_class = ExamMaterialRuleSerializer


@registerView("clinicalcharges")
class ClinicalChargeAPIView(BaseAPIView):
    """Made by the clinical flow only (clinical_billing_service), never here."""
    queryset = ClinicalCharge.objects.select_related("paciente__person")
    serializer_class = ClinicalChargeSerializer
    http_method_names = ["get", "head", "options"]


@registerView("materialconsumptions")
class MaterialConsumptionAPIView(BaseAPIView):
    """Made by the clinical flow only (clinical_billing_service), never here."""
    queryset = MaterialConsumption.objects.all()
    serializer_class = MaterialConsumptionSerializer
    http_method_names = ["get", "head", "options"]
