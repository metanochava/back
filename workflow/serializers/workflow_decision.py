from django_resaas.saas.core.base.serializers import BaseSerializer
from workflow.models import WorkflowDecision


class WorkflowDecisionSerializer(BaseSerializer):
    class Meta:
        model = WorkflowDecision
        fields = "__all__"
