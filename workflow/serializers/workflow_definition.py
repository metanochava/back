from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer
from workflow import registry, services
from workflow.models import WorkflowDefinition


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
