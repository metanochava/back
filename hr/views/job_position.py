# hr/views/job_position.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.job_position import JobPosition
from hr.serializers.job_position import JobPositionSerializer


@registerView('jobpositions', module='hr')
class JobPositionAPIView(BaseAPIView):
    queryset = JobPosition.objects.all()
    serializer_class = JobPositionSerializer