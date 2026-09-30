# hr/views/onboarding_template.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.onboarding_template import OnboardingTemplate
from hr.serializers.onboarding_template import OnboardingTemplateSerializer


@registerView('onboardingtemplates', module='hr')
class OnboardingTemplateAPIView(BaseAPIView):
    queryset = OnboardingTemplate.objects.all()
    serializer_class = OnboardingTemplateSerializer
