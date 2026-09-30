# hr/serializers/job_opening.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.department import Department
from hr.models.job_grade import JobGrade
from hr.models.job_opening import JobOpening
from hr.models.job_position import JobPosition
from hr.serializers.department import DepartmentSerializer
from hr.serializers.job_grade import JobGradeSerializer
from hr.serializers.job_position import JobPositionSerializer


class JobOpeningSerializer(BaseSerializer):

    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    department_data = DepartmentSerializer(source='department', read_only=True)

    position = serializers.PrimaryKeyRelatedField(
        queryset=JobPosition.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    position_data = JobPositionSerializer(source='position', read_only=True)

    job_grade = serializers.PrimaryKeyRelatedField(
        queryset=JobGrade.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    job_grade_data = JobGradeSerializer(source='job_grade', read_only=True)

    class Meta:
        model = JobOpening
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)

        # Same tenant-boundary pattern as EmployeeSerializer.validate()
        # (hr/serializers/employee.py): querysets above are deliberately
        # unscoped so a mismatch is attributed to the field, not just
        # silently invisible.
        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None

        if entity_id:
            for field_name in ("department", "position", "job_grade"):
                related = attrs.get(field_name)

                if related is not None and str(related.entity_id) != str(entity_id):
                    raise serializers.ValidationError({
                        field_name: "Does not belong to the current entity."
                    })

        return attrs
