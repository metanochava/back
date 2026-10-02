# hr/serializers/promotion.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.employee import Employee
from hr.models.job_position import JobPosition
from hr.models.job_grade import JobGrade
from hr.models.promotion import Promotion


class PromotionSerializer(BaseSerializer):

    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    employee_data = serializers.SerializerMethodField()

    previous_position = serializers.PrimaryKeyRelatedField(
        queryset=JobPosition.objects.all(), required=False, allow_null=True,
    )
    new_position = serializers.PrimaryKeyRelatedField(queryset=JobPosition.objects.all())
    previous_job_grade = serializers.PrimaryKeyRelatedField(
        queryset=JobGrade.objects.all(), required=False, allow_null=True,
    )
    new_job_grade = serializers.PrimaryKeyRelatedField(
        queryset=JobGrade.objects.all(), required=False, allow_null=True,
    )
    new_position_data = serializers.SerializerMethodField()
    new_job_grade_data = serializers.SerializerMethodField()

    class Meta:
        model = Promotion
        fields = "__all__"

    def get_employee_data(self, obj):
        return {"id": obj.employee_id, "label": str(obj.employee)}

    def get_new_position_data(self, obj):
        return {"id": obj.new_position_id, "label": str(obj.new_position)}

    def get_new_job_grade_data(self, obj):
        if not obj.new_job_grade_id:
            return None
        return {"id": obj.new_job_grade_id, "label": str(obj.new_job_grade)}
