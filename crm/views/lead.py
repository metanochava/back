from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action

from crm import services
from crm.models import Lead, Stage
from crm.serializers import LeadSerializer, OpportunitySerializer


@registerView("leads")
class LeadAPIView(BaseAPIView):
    queryset = Lead.objects.select_related("owner")
    serializer_class = LeadSerializer

    def _status(self, request, new_status):
        lead = services.change_lead_status(
            lead=self.get_object(), user=request.user, new_status=new_status, reason=request.data.get("reason")
        )
        return Response(self.get_serializer(lead).data)

    @resaas_action(methods=["post"], detail=True, label="Mark as contacted", icon="call", position="t", order=10, autorequest=True)
    def mark_contacted(self, request, pk=None):
        return self._status(request, Lead.STATUS_CONTACTED)

    @resaas_action(methods=["post"], detail=True, label="Qualify", icon="verified", position="t", order=20, autorequest=True)
    def qualify(self, request, pk=None):
        return self._status(request, Lead.STATUS_QUALIFIED)

    @resaas_action(
        methods=["post"], detail=True, label="Disqualify", icon="block",
        tooltip="Disqualify the lead (a reason is required)", position="t", order=30,
    )
    def disqualify(self, request, pk=None):
        return self._status(request, Lead.STATUS_DISQUALIFIED)

    @resaas_action(methods=["post"], detail=True, label="Reopen", icon="replay", position="t", order=40, autorequest=True)
    def reopen(self, request, pk=None):
        return self._status(request, Lead.STATUS_NEW)

    @resaas_action(
        methods=["post"], detail=True, label="Convert", icon="trending_up",
        tooltip="Create an opportunity from this lead", position="t", order=50,
    )
    def convert(self, request, pk=None):
        lead = self.get_object()
        stage = None
        if request.data.get("stage"):
            stage = Stage.objects.filter(id=request.data["stage"], entity_id=request.entity_id).first()
            if stage is None:
                raise ValidationError({"stage": ["Does not belong to the current entity."]})
        date = request.data.get("expected_close_date")
        parsed = parse_date(date) if date else None
        if date and parsed is None:
            raise ValidationError({"expected_close_date": ["Enter a valid date."]})

        opportunity = services.convert_lead(
            lead=lead,
            user=request.user,
            title=request.data.get("title"),
            amount=request.data.get("amount") or 0,
            stage=stage,
            customer_id=request.data.get("customer_id") or None,
            expected_close_date=parsed,
        )
        return Response(OpportunitySerializer(opportunity, context=self.get_serializer_context()).data)
