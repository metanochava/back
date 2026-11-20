"""The pedagogica API (PROTECTED, BaseAPIView: per action permission, the
Entity / Branch scope).

Staff: CRUD of lesson plans, lessons (the digital board), attachments,
materials, assignments, submissions (read + grade), calendar events, progress
notes and class messages; publish / unpublish a lesson; publish / close /
reopen an assignment; GET lessons/search/?q=&class_group=&subject=.

Students and guardians (the portal): GET <resource>/mine/?enrolment=<own>
for lessons (+ ?subject=&q=), materials, assignments (with the student's own
submission), calendar events, shared progress notes and class messages; POST
assignments/{id}/submit/ {enrolment, text?, file?}. "Own" is resolved by
academica.services.portal_service, never by the client.
"""
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action
from django_resaas.saas.core.exceptions import ResaasAPIException

from academica.services import portal_service
from pedagogica import models as m
from pedagogica import serializers as s
from pedagogica.services import assignment_service, lesson_service


class _Base(BaseAPIView):
    def perform_create(self, serializer):
        from django.db import IntegrityError, transaction

        try:
            with transaction.atomic():
                super().perform_create(serializer)
        except IntegrityError:
            raise ResaasAPIException("This record already exists.", code="already_exists", status_code=409)


def _own_enrolment(request):
    return portal_service.own_enrolment(request, request.query_params.get("enrolment") or request.data.get("enrolment"))


def _attachments(request, lesson):
    return s.LessonAttachmentSerializer(lesson.attachments.all(), many=True, context={"request": request}).data


@registerView("lessonplans")
class LessonPlanAPIView(_Base):
    queryset = m.LessonPlan.objects.select_related("class_group", "subject", "teacher__person")
    serializer_class = s.LessonPlanSerializer


@registerView("lessons")
class LessonAPIView(_Base):
    queryset = m.Lesson.objects.select_related("class_group", "subject", "teacher__person")
    serializer_class = s.LessonSerializer

    def perform_create(self, serializer):
        if not serializer.validated_data.get("teacher"):
            serializer.validated_data["teacher"] = assignment_service.teacher_of(self.request)
        super().perform_create(serializer)

    @resaas_action(detail=True, methods=["post"], label="Publish", icon="publish")
    def publish(self, request, pk=None):
        return Response(self.get_serializer(lesson_service.publish(lesson=self.get_object(), user=request.user)).data)

    @resaas_action(detail=True, methods=["post"], label="Unpublish", icon="unpublished")
    def unpublish(self, request, pk=None):
        return Response(self.get_serializer(lesson_service.unpublish(lesson=self.get_object(), user=request.user)).data)

    @resaas_action(detail=False, methods=["get"], label="Search lessons", icon="search", permission="list_lesson",
                   visible=False)
    def search(self, request):
        """?q=&class_group=&subject=: the lessons' history, newest first."""
        lessons = self.filter_queryset(self.get_queryset())
        if request.query_params.get("class_group"):
            lessons = lessons.filter(class_group_id=request.query_params["class_group"])
        if request.query_params.get("subject"):
            lessons = lessons.filter(subject_id=request.query_params["subject"])
        lessons = lesson_service.search(lessons, request.query_params.get("q"))[:200]
        return Response(self.get_serializer(lessons, many=True).data)

    @resaas_action(detail=False, methods=["get"], url_path="mine", label="My lessons", icon="history_edu",
                   permission="view_own_lesson", visible=False)
    def view_own(self, request):
        """?enrolment=&subject=&q=: the class's published lessons, newest first."""
        lessons = lesson_service.for_enrolment(_own_enrolment(request), subject_id=request.query_params.get("subject"),
                                               q=request.query_params.get("q"))[:200]
        return Response([{**self.get_serializer(lesson).data, "attachments": _attachments(request, lesson)}
                         for lesson in lessons])


@registerView("lessonattachments")
class LessonAttachmentAPIView(_Base):
    queryset = m.LessonAttachment.objects.select_related("lesson")
    serializer_class = s.LessonAttachmentSerializer


@registerView("materials")
class MaterialAPIView(_Base):
    queryset = m.Material.objects.select_related("subject", "class_group")
    serializer_class = s.MaterialSerializer

    @resaas_action(detail=False, methods=["get"], url_path="mine", label="My materials", icon="folder_open",
                   permission="view_own_material", visible=False)
    def view_own(self, request):
        enrolment = _own_enrolment(request)
        rows = m.Material.objects.filter(entity_id=enrolment.entity_id, published=True).filter(
            Q(class_group_id=enrolment.class_group_id) | Q(class_group__isnull=True,
                                                          subject__curriculum_items__grade_level_id=enrolment.grade_level_id)
        ).distinct().select_related("subject")
        return Response(self.get_serializer(rows, many=True).data)


@registerView("assignments")
class AssignmentAPIView(_Base):
    queryset = m.Assignment.objects.select_related("class_group", "subject", "teacher__person")
    serializer_class = s.AssignmentSerializer

    def perform_create(self, serializer):
        if not serializer.validated_data.get("teacher"):
            serializer.validated_data["teacher"] = assignment_service.teacher_of(self.request)
        super().perform_create(serializer)

    def _status(self, request, to):
        return Response(self.get_serializer(assignment_service.set_status(assignment=self.get_object(), status=to,
                                                                          user=request.user)).data)

    @resaas_action(detail=True, methods=["post"], label="Publish", icon="publish")
    def publish(self, request, pk=None):
        return self._status(request, m.Assignment.STATUS_PUBLISHED)

    @resaas_action(detail=True, methods=["post"], label="Close", icon="lock")
    def close(self, request, pk=None):
        return self._status(request, m.Assignment.STATUS_CLOSED)

    @resaas_action(detail=True, methods=["get"], label="Submissions", icon="inbox", permission="list_submission",
                   visible=False)
    def submissions(self, request, pk=None):
        rows = self.get_object().submissions.select_related("enrolment__student__person")
        return Response(s.SubmissionSerializer(rows, many=True, context={"request": request}).data)

    @resaas_action(detail=False, methods=["get"], url_path="mine", label="My assignments", icon="assignment",
                   permission="view_own_assignment", visible=False)
    def view_own(self, request):
        """The class's published / closed assignments, each with the student's submission."""
        enrolment = _own_enrolment(request)
        rows = (m.Assignment.objects.filter(class_group_id=enrolment.class_group_id)
                .exclude(status=m.Assignment.STATUS_DRAFT).select_related("subject"))
        mine = {sub.assignment_id: sub for sub in m.Submission.objects.filter(enrolment=enrolment, assignment__in=rows)}
        return Response([{**self.get_serializer(a).data,
                          "submission": (s.SubmissionSerializer(mine[a.id], context={"request": request}).data
                                         if a.id in mine else None)} for a in rows])

    @resaas_action(detail=True, methods=["post"], label="Submit", icon="send", permission="submit_assignment",
                   visible=False)
    def submit(self, request, pk=None):
        """{enrolment, text?, file?}: the caller's own enrolment submits once."""
        enrolment = portal_service.own_enrolment(request, request.data.get("enrolment"))
        assignment = m.Assignment.objects.filter(id=pk, entity_id=request.entity_id).first()
        if assignment is None:
            raise ResaasAPIException("Assignment not found.", code="not_found", status_code=404)
        submission = assignment_service.submit(request=request, assignment=assignment, enrolment=enrolment,
                                               text=request.data.get("text", ""), file=request.FILES.get("file"))
        return Response(s.SubmissionSerializer(submission, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)


@registerView("submissions")
class SubmissionAPIView(_Base):
    """Created by assignments/{id}/submit/ only; graded here."""

    queryset = m.Submission.objects.select_related("assignment", "enrolment__student__person")
    serializer_class = s.SubmissionSerializer
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        from rest_framework.exceptions import MethodNotAllowed
        raise MethodNotAllowed("POST")

    @resaas_action(detail=True, methods=["post"], label="Grade", icon="grading")
    def grade(self, request, pk=None):
        """{score, feedback?}: 0 to the assignment's maximum; the academica grade follows."""
        submission = assignment_service.grade(request=request, submission=self.get_object(),
                                              score=request.data.get("score"), feedback=request.data.get("feedback", ""))
        return Response(self.get_serializer(submission).data)


def _own_list(view, request, rows):
    return Response(view.get_serializer(rows, many=True).data)


@registerView("calendarevents")
class CalendarEventAPIView(_Base):
    queryset = m.CalendarEvent.objects.select_related("class_group", "subject")
    serializer_class = s.CalendarEventSerializer

    @resaas_action(detail=False, methods=["get"], url_path="mine", label="My calendar", icon="event",
                   permission="view_own_calendarevent", visible=False)
    def view_own(self, request):
        enrolment = _own_enrolment(request)
        rows = m.CalendarEvent.objects.filter(entity_id=enrolment.entity_id, branch_id=enrolment.branch_id).filter(
            Q(class_group_id=enrolment.class_group_id) | Q(class_group__isnull=True))
        return _own_list(self, request, rows)


@registerView("progressnotes")
class ProgressNoteAPIView(_Base):
    queryset = m.ProgressNote.objects.select_related("enrolment__student__person", "subject")
    serializer_class = s.ProgressNoteSerializer

    def perform_create(self, serializer):
        if not serializer.validated_data.get("teacher"):
            serializer.validated_data["teacher"] = assignment_service.teacher_of(self.request)
        super().perform_create(serializer)

    @resaas_action(detail=False, methods=["get"], url_path="mine", label="My progress", icon="insights",
                   permission="view_own_progressnote", visible=False)
    def view_own(self, request):
        """Only the notes the teachers shared."""
        return _own_list(self, request, m.ProgressNote.objects.filter(enrolment=_own_enrolment(request), shared=True))


@registerView("classmessages")
class ClassMessageAPIView(_Base):
    queryset = m.ClassMessage.objects.select_related("class_group", "subject")
    serializer_class = s.ClassMessageSerializer

    @resaas_action(detail=False, methods=["get"], url_path="mine", label="My class messages", icon="campaign",
                   permission="view_own_classmessage", visible=False)
    def view_own(self, request):
        enrolment = _own_enrolment(request)
        return _own_list(self, request, m.ClassMessage.objects.filter(class_group_id=enrolment.class_group_id,
                                                                      published=True))
