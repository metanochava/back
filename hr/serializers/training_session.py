# hr/serializers/training_session.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.course import Course
from hr.models.training_session import TrainingSession


class TrainingSessionSerializer(BaseSerializer):

    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())
    course_data = serializers.SerializerMethodField()

    enrolled_count = serializers.SerializerMethodField()

    class Meta:
        model = TrainingSession
        fields = "__all__"

    def get_course_data(self, obj):
        return {"id": obj.course_id, "label": str(obj.course)}

    def get_enrolled_count(self, obj):
        return obj.enrollments.exclude(status="dropped").count()

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None

        course = attrs.get("course")
        if entity_id and course is not None and str(course.entity_id) != str(entity_id):
            raise serializers.ValidationError({
                "course": "Does not belong to the current entity."
            })

        return attrs
