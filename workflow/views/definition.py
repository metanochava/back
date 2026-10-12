from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.exceptions import ConflictError

from workflow.models import WorkflowDefinition, WorkflowStep
from workflow.serializers import WorkflowDefinitionSerializer, WorkflowStepSerializer


@registerView("definitions")
class WorkflowDefinitionAPIView(BaseAPIView):
    queryset = WorkflowDefinition.objects.all()
    serializer_class = WorkflowDefinitionSerializer

    def perform_destroy(self, instance):
        if instance.instances.exists():
            raise ConflictError("A workflow with approvals cannot be deleted; make it inactive.", code="workflow_in_use")
        super().perform_destroy(instance)


@registerView("steps")
class WorkflowStepAPIView(BaseAPIView):
    queryset = WorkflowStep.objects.select_related("definition")
    serializer_class = WorkflowStepSerializer
