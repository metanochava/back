# hr/views/job_grade.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.job_grade import JobGrade
from hr.serializers.job_grade import JobGradeSerializer


@registerView('jobgrades', module='hr')
class JobGradeAPIView(BaseAPIView):
    queryset = JobGrade.objects.all()
    serializer_class = JobGradeSerializer
