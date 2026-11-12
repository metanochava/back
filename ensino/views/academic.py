"""Teaching, assessments, grades (recorded / amended through
grading_service), attendance and tuition rules / charges."""
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action
from django_resaas.saas.core.exceptions import ResaasAPIException

from ensino import models as m
from ensino import serializers as s
from ensino.views._conflict import UniqueConflictMixin
from ensino.services import grading_service, tuition_service


@registerView("teachingassignments")
class TeachingAssignmentAPIView(UniqueConflictMixin, BaseAPIView):
    queryset = m.TeachingAssignment.objects.select_related("class_group", "subject", "teacher__person")
    serializer_class = s.TeachingAssignmentSerializer


@registerView("assessments")
class AssessmentAPIView(UniqueConflictMixin, BaseAPIView):
    queryset = m.Assessment.objects.select_related("class_group", "subject", "period")
    serializer_class = s.AssessmentSerializer


@registerView("grades")
class GradeAPIView(UniqueConflictMixin, BaseAPIView):
    queryset = m.Grade.objects.select_related("assessment", "enrolment__student__person")
    serializer_class = s.GradeSerializer

    def perform_create(self, serializer):
        d = serializer.validated_data
        serializer.instance = grading_service.record(
            request=self.request, assessment=d["assessment"], enrolment=d["enrolment"], value=d.get("value"),
            qualitative_value=d.get("qualitative_value", ""), absent=d.get("absent", False), comment=d.get("comment", ""),
        )

    def perform_update(self, serializer):
        # a recorded grade changes only with a reason (kept in GradeRevision)
        d, grade = serializer.validated_data, serializer.instance
        serializer.instance = grading_service.amend(
            request=self.request, grade=grade, value=d.get("value", grade.value),
            qualitative_value=d.get("qualitative_value", grade.qualitative_value),
            absent=d.get("absent", grade.absent), reason=self.request.data.get("reason", ""), comment=d.get("comment"),
        )

    def perform_destroy(self, instance):
        raise ResaasAPIException("A recorded grade is amended, never deleted.", code="grade_not_deletable",
                                 status_code=status.HTTP_409_CONFLICT)

    @resaas_action(detail=True, methods=["get"], label="Grade history", icon="history", permission="view_grade",
                   visible=False)
    def history(self, request, pk=None):
        rows = self.get_object().revisions.order_by("created_at")
        return Response(s.GradeRevisionSerializer(rows, many=True, context={"request": request}).data)


@registerView("studentattendances")
class StudentAttendanceAPIView(UniqueConflictMixin, BaseAPIView):
    queryset = m.StudentAttendance.objects.select_related("enrolment__student__person", "subject")
    serializer_class = s.StudentAttendanceSerializer

    @resaas_action(detail=False, methods=["post"], label="Record class attendance", icon="fact_check",
                   permission="add_studentattendance", visible=False)
    @transaction.atomic
    def record_class(self, request):
        """{class_group, date, subject?, rows: [{enrolment, status, justification?}]} - one call for the
        whole class; an existing record of that enrolment, date and subject is updated."""
        class_group = m.ClassGroup.objects.filter(id=request.data.get("class_group"), entity_id=request.entity_id).first()
        if class_group is None:
            raise ResaasAPIException("Choose a class.", code="invalid", details={"class_group": ["Choose a class."]})
        subject_id = request.data.get("subject") or None
        date = request.data.get("date")
        valid = {str(e.id): e for e in class_group.enrolments.filter(status=m.Enrolment.STATUS_ACTIVE)}
        statuses = dict(m.StudentAttendance.STATUS_CHOICES)
        saved = 0
        for row in request.data.get("rows") or []:
            enrolment = valid.get(str(row.get("enrolment")))
            if enrolment is None or row.get("status") not in statuses:
                raise ResaasAPIException("A row is not an active student of the class, or its status is invalid.",
                                         code="invalid", details={"rows": [str(row.get("enrolment"))]})
            m.StudentAttendance.objects.update_or_create(
                enrolment=enrolment, date=date, subject_id=subject_id,
                defaults={"status": row["status"], "justification": row.get("justification", ""),
                          "entity_id": request.entity_id, "branch_id": request.branch_id,
                          "updated_by": request.user, "created_by": request.user, "state": "Active"},
            )
            saved += 1
        return Response({"saved": saved})


@registerView("tuitionrules")
class TuitionRuleAPIView(UniqueConflictMixin, BaseAPIView):
    queryset = m.TuitionRule.objects.select_related("programme", "grade_level")
    serializer_class = s.TuitionRuleSerializer
    cross_branch_actions = ["list", "retrieve"]


@registerView("tuitioncharges")
class TuitionChargeAPIView(UniqueConflictMixin, BaseAPIView):
    """Made by the enrolment flow / charge_month only."""
    queryset = m.TuitionCharge.objects.select_related("enrolment__student__person")
    serializer_class = s.TuitionChargeSerializer
    http_method_names = ["get", "head", "options"]
