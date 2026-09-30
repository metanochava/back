# hr/serializers/performance_review.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.employee import Employee
from hr.models.performance_cycle import PerformanceCycle
from hr.models.performance_review import PerformanceReview
from hr.serializers.review_competency_rating import (
    ReviewCompetencyRatingSerializer,
)


class PerformanceReviewSerializer(BaseSerializer):

    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    employee_data = serializers.SerializerMethodField()

    cycle = serializers.PrimaryKeyRelatedField(queryset=PerformanceCycle.objects.all())
    cycle_data = serializers.SerializerMethodField()

    reviewer = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True,
    )
    reviewer_data = serializers.SerializerMethodField()

    competency_ratings = ReviewCompetencyRatingSerializer(many=True, read_only=True)

    class Meta:
        model = PerformanceReview
        fields = "__all__"
        # status/submitted_at only change through the submit_review action
        # (hr/services/performance_service.py) - a submitted review is
        # immutable history, same rule as Contract/Payslip elsewhere.
        extra_kwargs = {
            'status': {'read_only': True},
            'submitted_at': {'read_only': True},
        }

    def get_employee_data(self, obj):
        return {"id": obj.employee_id, "label": str(obj.employee)}

    def get_cycle_data(self, obj):
        return {"id": obj.cycle_id, "label": str(obj.cycle)}

    def get_reviewer_data(self, obj):
        if not obj.reviewer_id:
            return None
        return {"id": obj.reviewer_id, "label": str(obj.reviewer)}

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None

        if entity_id:
            for field_name in ("employee", "cycle", "reviewer"):
                related = attrs.get(field_name)

                if related is not None and str(related.entity_id) != str(entity_id):
                    raise serializers.ValidationError({
                        field_name: "Does not belong to the current entity."
                    })

        return attrs
