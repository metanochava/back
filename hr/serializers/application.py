# hr/serializers/application.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.application import Application
from hr.models.candidate import Candidate
from hr.models.job_opening import JobOpening
from hr.serializers.candidate import CandidateSerializer
from hr.serializers.job_opening import JobOpeningSerializer


class ApplicationSerializer(BaseSerializer):

    job_opening = serializers.PrimaryKeyRelatedField(
        queryset=JobOpening.objects.all(),
        write_only=True,
    )
    job_opening_data = JobOpeningSerializer(source='job_opening', read_only=True)

    candidate = serializers.PrimaryKeyRelatedField(
        queryset=Candidate.objects.all(),
        write_only=True,
    )
    candidate_data = CandidateSerializer(source='candidate', read_only=True)

    employee_data = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = "__all__"
        # status/employee only change through the move/schedule_interview/
        # hire actions (ApplicationAPIView, backed by
        # hr/services/recruitment_service.py) - same "workflow via
        # actions, not free PATCH" rule LeaveRequest follows (pedido
        # secção 49).
        extra_kwargs = {
            'status': {'read_only': True},
            'employee': {'read_only': True},
        }

    def get_employee_data(self, obj):
        if not obj.employee_id:
            return None
        return {"id": obj.employee_id, "label": str(obj.employee)}

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None

        if entity_id:
            for field_name in ("job_opening", "candidate"):
                related = attrs.get(field_name)

                if related is not None and str(related.entity_id) != str(entity_id):
                    raise serializers.ValidationError({
                        field_name: "Does not belong to the current entity."
                    })

        return attrs
