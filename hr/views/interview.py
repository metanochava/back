# hr/views/interview.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.interview import Interview
from hr.serializers.interview import InterviewSerializer


@registerView('interviews', module='hr')
class InterviewAPIView(BaseAPIView):
    queryset = Interview.objects.all()
    serializer_class = InterviewSerializer
