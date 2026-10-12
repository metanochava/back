from rest_framework import status
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action
from django_resaas.saas.core.exceptions import ConflictError

from crm import services
from crm.models import Stage
from crm.serializers import StageSerializer


@registerView("stages")
class StageAPIView(BaseAPIView):
    queryset = Stage.objects.all()
    serializer_class = StageSerializer

    def perform_destroy(self, instance):
        if instance.opportunities.exists():
            raise ConflictError("A stage with opportunities cannot be deleted; make it inactive.", code="stage_in_use")
        super().perform_destroy(instance)

    @resaas_action(
        methods=["post"], detail=False, label="Create default stages", icon="playlist_add",
        tooltip="Create the usual pipeline stages", position="l", order=10, autorequest=True,
    )
    def create_defaults(self, request):
        stages = services.create_default_stages(
            entity_id=request.entity_id, branch_id=request.branch_id, user=request.user
        )
        return Response(self.get_serializer(stages, many=True).data, status=status.HTTP_201_CREATED)
