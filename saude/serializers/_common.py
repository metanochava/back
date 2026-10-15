from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


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
