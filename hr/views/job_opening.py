# hr/views/job_opening.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.job_opening import JobOpening
from hr.serializers.job_opening import JobOpeningSerializer


@registerView('jobopenings', module='hr')
class JobOpeningAPIView(BaseAPIView):
    queryset = JobOpening.objects.all()
    serializer_class = JobOpeningSerializer
