from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer
from workflow.models import WorkflowStep


class WorkflowStepSerializer(BaseSerializer):
    class Meta:
        model = WorkflowStep
        fields = "__all__"

    def validate_approver_permission(self, value):
        from django.contrib.auth.models import Permission

        if not Permission.objects.filter(codename=value).exists():
            raise serializers.ValidationError("This permission does not exist.")
        return value
