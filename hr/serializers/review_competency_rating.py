# hr/serializers/review_competency_rating.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.performance_review import PerformanceReview
from hr.models.competency import Competency
from hr.models.review_competency_rating import ReviewCompetencyRating


class ReviewCompetencyRatingSerializer(BaseSerializer):

    review = serializers.PrimaryKeyRelatedField(queryset=PerformanceReview.objects.all())

    competency = serializers.PrimaryKeyRelatedField(queryset=Competency.objects.all())
    competency_data = serializers.SerializerMethodField()

    class Meta:
        model = ReviewCompetencyRating
        fields = "__all__"

    def get_competency_data(self, obj):
        return {"id": obj.competency_id, "label": str(obj.competency)}

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None

        if entity_id:
            for field_name in ("review", "competency"):
                related = attrs.get(field_name)

                if related is not None and str(related.entity_id) != str(entity_id):
                    raise serializers.ValidationError({
                        field_name: "Does not belong to the current entity."
                    })

        return attrs
