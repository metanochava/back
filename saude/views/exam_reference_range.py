from django_resaas.saas.core.base.views import BaseAPIView, registerView
from saude.models.exam_reference_range import ExamReferenceRange
from saude.serializers.exam_reference_range import ExamReferenceRangeSerializer


@registerView("examreferenceranges")
class ExamReferenceRangeAPIView(BaseAPIView):
    """Reference ranges of numeric parameters (configuration - never
    seeded with clinical values)."""

    queryset = ExamReferenceRange.objects.select_related("parameter")
    serializer_class = ExamReferenceRangeSerializer
