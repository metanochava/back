from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from saude.models.exam_parameter import ExamParameter, ExamReferenceRange


def _run_model_clean(serializer, attrs):
    """Applies the model's own clean() rules to the merged instance state."""
    instance = serializer.instance or serializer.Meta.model()
    for name, value in attrs.items():
        setattr(instance, name, value)
    try:
        instance.clean()
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.message_dict)
    return attrs


class ExamParameterSerializer(BaseSerializer):

    class Meta:
        model = ExamParameter
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        return _run_model_clean(self, attrs)


class ExamReferenceRangeSerializer(BaseSerializer):

    class Meta:
        model = ExamReferenceRange
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        return _run_model_clean(self, attrs)
