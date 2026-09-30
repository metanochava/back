# hr/views/competency.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.competency import Competency
from hr.serializers.competency import CompetencySerializer


@registerView('competencies', module='hr')
class CompetencyAPIView(BaseAPIView):
    queryset = Competency.objects.all()
    serializer_class = CompetencySerializer
