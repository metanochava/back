from django_resaas.saas.core.base.views import BaseAPIView, registerView
from saude.models.exam_parameter import ExamParameter
from saude.serializers.exam_parameter import ExamParameterSerializer


@registerView("examparameters")
class ExamParameterAPIView(BaseAPIView):
    """Parameters of an exam definition (configuration)."""

    queryset = ExamParameter.objects.select_related("exame")
    serializer_class = ExamParameterSerializer
