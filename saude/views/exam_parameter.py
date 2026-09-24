from django_resaas.saas.core.base.views import BaseAPIView, registerView

from saude.models.exam_parameter import ExamParameter, ExamReferenceRange
from saude.serializers.exam_parameter import ExamParameterSerializer, ExamReferenceRangeSerializer


@registerView("examparameters")
class ExamParameterAPIView(BaseAPIView):
    """Parameters of an exam definition (configuration)."""

    queryset = ExamParameter.objects.select_related("exame")
    serializer_class = ExamParameterSerializer


@registerView("examreferenceranges")
class ExamReferenceRangeAPIView(BaseAPIView):
    """Reference ranges of numeric parameters (configuration - never
    seeded with clinical values)."""

    queryset = ExamReferenceRange.objects.select_related("parameter")
    serializer_class = ExamReferenceRangeSerializer
