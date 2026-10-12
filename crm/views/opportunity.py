from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action

from crm import services
from crm.models import Opportunity, Stage
from crm.serializers import OpportunitySerializer


@registerView("opportunities")
class OpportunityAPIView(BaseAPIView):
    queryset = Opportunity.objects.select_related("stage", "lead", "owner")
    serializer_class = OpportunitySerializer

    @resaas_action(
        methods=["post"], detail=True, label="Move", icon="swap_horiz",
        tooltip="Move the opportunity to another stage", position="t", order=10,
    )
    def move(self, request, pk=None):
        opportunity = self.get_object()
        stage = Stage.objects.filter(id=request.data.get("stage"), entity_id=request.entity_id).first() if request.data.get("stage") else None
        if stage is None:
            raise ValidationError({"stage": ["This field is required."]})
        opportunity = services.move_opportunity(
            opportunity=opportunity, user=request.user, stage=stage, lost_reason=request.data.get("lost_reason")
        )
        return Response(self.get_serializer(opportunity).data)

    @resaas_action(
        methods=["get"], detail=False, label="Pipeline", icon="view_kanban",
        tooltip="Open opportunities per stage", position="l", order=20,
    )
    def pipeline(self, request):
        """GET ?mine=true limits the summary to the current user's opportunities."""
        owner = request.user if request.query_params.get("mine") in ("1", "true") else None
        return Response(services.pipeline_summary(request.entity_id, owner=owner))
