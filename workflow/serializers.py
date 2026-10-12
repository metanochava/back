from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from workflow import registry, services
from workflow.models import WorkflowDecision, WorkflowDefinition, WorkflowInstance, WorkflowStep


class WorkflowDefinitionSerializer(BaseSerializer):
    class Meta:
        model = WorkflowDefinition
        fields = "__all__"

    def get_fields(self):
        fields = super().get_fields()
        # choices come from the code registry (what modules made available)
        fields["on_approved_action"] = serializers.ChoiceField(
            choices=registry.action_choices(), required=False, allow_null=True, allow_blank=True,
            label="On approval",
        )
        fields["target_model"] = serializers.ChoiceField(choices=services.target_choices(), label="Target")
        return fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        services.validate_definition(
            attrs.get("target_model", getattr(self.instance, "target_model", None)),
            attrs.get("on_approved_action", getattr(self.instance, "on_approved_action", None)),
        )
        return attrs


class WorkflowStepSerializer(BaseSerializer):
    class Meta:
        model = WorkflowStep
        fields = "__all__"

    def validate_approver_permission(self, value):
        from django.contrib.auth.models import Permission

        if not Permission.objects.filter(codename=value).exists():
            raise serializers.ValidationError("This permission does not exist.")
        return value


class WorkflowDecisionSerializer(BaseSerializer):
    class Meta:
        model = WorkflowDecision
        fields = "__all__"


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
