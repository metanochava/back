from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action

from crm import services
from crm.models import Activity
from crm.serializers import ActivitySerializer


@registerView("activities")
class ActivityAPIView(BaseAPIView):
    queryset = Activity.objects.select_related("lead", "opportunity", "assigned_to")
    serializer_class = ActivitySerializer

    @resaas_action(methods=["post"], detail=True, label="Mark as done", icon="check", position="t", order=10, autorequest=True)
    def complete(self, request, pk=None):
        activity = services.complete_activity(activity=self.get_object(), user=request.user)
        return Response(self.get_serializer(activity).data)
