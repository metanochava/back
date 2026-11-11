from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from django_resaas.saas.core.utils.translate import Translate
from saude.models.examemedico import ExameMedico
from saude.models.examset import ExamSet

SCOPES = ("mine", "entity")


class ExamSetSerializer(BaseSerializer):
    """READ: {id, name, exams: [exam ids], scope: mine|entity}. WRITE: name,
    exams and, on create, scope (the server turns it into the owner)."""

    exams = serializers.PrimaryKeyRelatedField(queryset=ExameMedico.objects.all(), many=True)
    scope = serializers.ChoiceField(choices=SCOPES, write_only=True, required=False, default="mine")

    class Meta:
        model = ExamSet
        fields = ["id", "name", "exams", "scope"]

    def to_representation(self, instance):
        return {
            "id": str(instance.id),
            "name": instance.name,
            "exams": [str(e.id) for e in instance.exams.all()],
            "scope": "entity" if instance.owner_id is None else "mine",
        }

    def _error(self, field, message):
        request = self.context.get("request")
        return serializers.ValidationError({field: [Translate.tdc(request, message)]})

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise self._error("name", "Give the set a name.")
        return value

    def validate_exams(self, value):
        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None)
        # the catalogue is the Entity's: an exam of another one is refused
        if any(str(exam.entity_id) != str(entity_id) for exam in value):
            raise self._error("exams", "Choose exams of this clinic's catalogue.")
        if not value:
            raise self._error("exams", "Add at least one exam to the set.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        name = attrs.get("name", getattr(self.instance, "name", None))
        if self.instance is not None:
            owner_id = self.instance.owner_id
        else:
            owner_id = None if attrs.get("scope") == "entity" else request.user.id
        clash = ExamSet.objects.filter(entity_id=request.entity_id, name__iexact=name, owner_id=owner_id)
        if self.instance is not None:
            clash = clash.exclude(id=self.instance.id)
        if clash.exists():
            raise self._error("name", "There is already a set with this name.")
        return attrs
