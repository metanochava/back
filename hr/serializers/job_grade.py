# hr/serializers/job_grade.py

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.job_grade import JobGrade


class JobGradeSerializer(BaseSerializer):

    class Meta:
        model = JobGrade
        fields = "__all__"
