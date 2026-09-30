# hr/serializers/onboarding_template_task.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.onboarding_template import OnboardingTemplate
from hr.models.onboarding_template_task import OnboardingTemplateTask


class OnboardingTemplateTaskSerializer(BaseSerializer):

    template = serializers.PrimaryKeyRelatedField(queryset=OnboardingTemplate.objects.all())
    template_data = serializers.SerializerMethodField()

    class Meta:
        model = OnboardingTemplateTask
        fields = "__all__"

    def get_template_data(self, obj):
        return {"id": obj.template_id, "label": str(obj.template)}

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None

        template = attrs.get("template")
        if entity_id and template is not None and str(template.entity_id) != str(entity_id):
            raise serializers.ValidationError({
                "template": "Does not belong to the current entity."
            })

        return attrs
