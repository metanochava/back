from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from pedagogica import models as m
from pedagogica.services import lesson_service

RELATIONS = ("class_group", "subject", "teacher", "plan", "period", "lesson", "assessment", "enrolment", "assignment")


class _TenantSerializer(BaseSerializer):
    """Every related record (class, subject, teacher, ...) is of the
    request's Entity; no automatic unique validators (the views answer 409)."""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        entity_id = str(getattr(request, "entity_id", "") or "")
        for key in RELATIONS:
            obj = attrs.get(key)
            if obj is not None and entity_id and str(getattr(obj, "entity_id", entity_id)) != entity_id:
                raise serializers.ValidationError({key: ["Does not belong to the current entity."]})
        return attrs


def _meta(model, read_only=()):
    return type("Meta", (), {"model": model, "fields": "__all__", "validators": [], "read_only_fields": list(read_only)})


class LessonPlanSerializer(_TenantSerializer):
    Meta = _meta(m.LessonPlan)


class LessonSerializer(_TenantSerializer):
    """blocks: the digital board's content (lesson_service.clean_blocks);
    search_text, status and published_at are the server's."""

    Meta = _meta(m.Lesson, ("search_text", "status", "published_at"))

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if "blocks" in attrs:
            attrs["blocks"] = lesson_service.clean_blocks(attrs["blocks"])
        current = self.instance
        attrs["search_text"] = lesson_service.search_text(
            attrs.get("title", getattr(current, "title", "")), attrs.get("summary", getattr(current, "summary", "")),
            attrs.get("blocks", getattr(current, "blocks", [])))
        return attrs


class LessonAttachmentSerializer(_TenantSerializer):
    Meta = _meta(m.LessonAttachment)


class MaterialSerializer(_TenantSerializer):
    Meta = _meta(m.Material)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        current = self.instance
        if not attrs.get("file", getattr(current, "file", None)) and not attrs.get("link", getattr(current, "link", "")):
            raise serializers.ValidationError({"file": ["Attach a file or give a link."]})
        return attrs


class AssignmentSerializer(_TenantSerializer):
    Meta = _meta(m.Assignment, ("status",))

    def validate(self, attrs):
        attrs = super().validate(attrs)
        assessment, class_group = attrs.get("assessment"), attrs.get("class_group")
        if assessment is not None and class_group is not None and assessment.class_group_id != class_group.id:
            raise serializers.ValidationError({"assessment": ["Choose an assessment of this class."]})
        return attrs


class SubmissionSerializer(_TenantSerializer):
    student_name = serializers.CharField(source="enrolment.student.person.full_name", read_only=True)

    Meta = _meta(m.Submission, ("assignment", "enrolment", "status", "submitted_at", "score", "feedback",
                                "graded_by", "graded_at"))


class CalendarEventSerializer(_TenantSerializer):
    Meta = _meta(m.CalendarEvent)


class ProgressNoteSerializer(_TenantSerializer):
    Meta = _meta(m.ProgressNote)


class ClassMessageSerializer(_TenantSerializer):
    Meta = _meta(m.ClassMessage)
