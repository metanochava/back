from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.exam_reference_range import ExamReferenceRange
from saude.serializers._common import _run_model_clean


class ExamReferenceRangeSerializer(BaseSerializer):

    class Meta:
        model = ExamReferenceRange
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        return _run_model_clean(self, attrs)
