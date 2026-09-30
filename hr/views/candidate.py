# hr/views/candidate.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.candidate import Candidate
from hr.serializers.candidate import CandidateSerializer


@registerView('candidates', module='hr')
class CandidateAPIView(BaseAPIView):
    queryset = Candidate.objects.all()
    serializer_class = CandidateSerializer
