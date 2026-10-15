from django_resaas.saas.core.base.views import BaseAPIView, registerView
from workflow.models import WorkflowStep
from workflow.serializers import WorkflowStepSerializer


@registerView("steps")
class WorkflowStepAPIView(BaseAPIView):
    queryset = WorkflowStep.objects.select_related("definition")
    serializer_class = WorkflowStepSerializer
