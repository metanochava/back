from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.exam_parameter import ExamParameter
from saude.serializers._common import _run_model_clean


class ExamParameterSerializer(BaseSerializer):

    class Meta:
        model = ExamParameter
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        return _run_model_clean(self, attrs)
