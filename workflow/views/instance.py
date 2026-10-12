from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action
from django_resaas.saas.core.services.group_access_service import held_codenames

from workflow import services
from workflow.models import WorkflowDefinition, WorkflowInstance
from workflow.serializers import WorkflowInstanceSerializer


@registerView("instances")
class WorkflowInstanceAPIView(BaseAPIView):
    """Approval requests. Created only with POST (definition + object_id),
    never edited: decide / cancel are the domain actions."""

    queryset = WorkflowInstance.objects.select_related("definition", "current_step").prefetch_related("decisions")
    serializer_class = WorkflowInstanceSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if getattr(self.request, "user", None) is not None and getattr(self.request, "entity_id", None):
            context["held"] = held_codenames(self.request)
        return context

    def create(self, request, *args, **kwargs):
        definition = WorkflowDefinition.objects.filter(
            id=request.data.get("definition"), entity_id=request.entity_id
        ).first()
        if definition is None:
            raise ValidationError({"definition": ["Does not belong to the current entity."]})
        instance = services.start_instance(
            definition=definition, object_id=request.data.get("object_id"), user=request.user
        )
        return Response(self.get_serializer(instance).data, status=201)

    @resaas_action(
        methods=["post"], detail=True, label="Decide", icon="how_to_vote",
        tooltip="Approve or reject the current step", position="t", order=10,
    )
    def decide(self, request, pk=None):
        instance = services.decide(
            instance=self.get_object(),
            user=request.user,
            held=held_codenames(request),
            decision=request.data.get("decision"),
            comment=request.data.get("comment"),
        )
        instance.refresh_from_db()
        return Response(self.get_serializer(instance).data)

    @resaas_action(
        methods=["post"], detail=True, label="Cancel", icon="cancel",
        tooltip="Cancel the approval request", position="t", order=20,
    )
    def cancel(self, request, pk=None):
        instance = services.cancel(
            instance=self.get_object(),
            user=request.user,
            can_cancel_any="cancel_any_workflowinstance" in held_codenames(request),
        )
        return Response(self.get_serializer(instance).data)

    @resaas_action(
        methods=["get"], detail=False, label="My approvals", icon="inbox",
        tooltip="Approval requests waiting for my decision", position="l", order=30,
    )
    def inbox(self, request):
        held = held_codenames(request)
        rows = services.inbox(entity_id=request.entity_id, user=request.user, held=held)
        return Response(self.get_serializer(rows, many=True).data)
