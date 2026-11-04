from django.db import IntegrityError, transaction
from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from django_resaas.saas.core.utils.translate import Translate
from saude.models.favouriteexam import FavouriteExam


class FavouriteExamSerializer(BaseSerializer):

    class Meta:
        model = FavouriteExam
        fields = "__all__"

    def _already_listed(self):
        request = self.context.get("request")
        message = Translate.tdc(request, "This exam is already in the favourites.")
        return serializers.ValidationError({"exame": [message]})

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None)
        exame = attrs.get("exame")
        if entity_id and exame and FavouriteExam.objects.filter(entity_id=entity_id, exame=exame).exists():
            raise self._already_listed()
        return attrs

    def create(self, validated_data):
        # two people adding the same exam at once: the constraint decides
        try:
            with transaction.atomic():
                return super().create(validated_data)
        except IntegrityError:
            raise self._already_listed()
