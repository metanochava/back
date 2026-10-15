from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer
from workflow import services
from workflow.models import WorkflowInstance
from workflow.serializers.workflow_decision import WorkflowDecisionSerializer


class WorkflowInstanceSerializer(BaseSerializer):
    decisions = WorkflowDecisionSerializer(many=True, read_only=True)
    can_decide = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowInstance
        fields = "__all__"

    def get_can_decide(self, obj):
        request = self.context.get("request")
        held = self.context.get("held")
        if request is None or held is None:
            return False
        return services.can_decide(obj, request.user, held)[0]
