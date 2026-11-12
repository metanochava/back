"""Students, guardians and enrolments. A student is registered with its
Person in one step (register); a guardian is added through the service (one
paying guardian); an enrolment is created and changes status only through
enrolment_service - never a PATCH of its status."""
import json

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from django_resaas.saas.core.base.permissions import isPermited
from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action
from django_resaas.saas.core.exceptions import ResaasAPIException
from django_resaas.saas.core.services.person_registration_service import documents_with_files

from ensino import models as m
from ensino import serializers as s
from ensino.views._conflict import UniqueConflictMixin
from ensino.services import enrolment_service, grading_service, student_service, tuition_service


@registerView("students")
class StudentAPIView(UniqueConflictMixin, BaseAPIView):
    queryset = m.Student.objects.select_related("person")
    serializer_class = s.StudentSerializer
    cross_branch_actions = ["list", "retrieve"]

    def create(self, request, *args, **kwargs):
        raise ResaasAPIException("Register a student with the register action.", code="use_register",
                                 status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

    @resaas_action(detail=False, methods=["post"], label="Register student", icon="person_add",
                   permission="add_student", visible=False)
    def register(self, request):
        """multipart or JSON: payload = {person_id | person, documents, contacts, admission_date, notes,
        guardians: [{person_id, relationship, pays, emergency_contact, can_pick_up}]}"""
        raw = request.data.get("payload")
        try:
            payload = json.loads(raw) if isinstance(raw, str) else (raw or request.data)
        except (TypeError, ValueError):
            raise ResaasAPIException("Invalid payload.", code="invalid_payload")
        needed = (["add_person"] if not payload.get("person_id") else []) \
            + (["add_document"] if payload.get("documents") else []) \
            + (["add_personcontact"] if payload.get("contacts") else []) \
            + (["add_guardian"] if payload.get("guardians") else [])
        missing = [p for p in needed if not isPermited(request=request, role=p)]
        if missing:
            raise ResaasAPIException(f"Missing permission(s): {', '.join(missing)}.", code="permission_denied",
                                     status_code=403)
        student = student_service.register_student(
            request=request, person_id=payload.get("person_id"), person_data=payload.get("person"),
            photo=request.FILES.get("person_photo"), documents=documents_with_files(request, payload.get("documents") or []),
            contacts=payload.get("contacts"), admission_date=payload.get("admission_date"),
            notes=payload.get("notes", ""), guardians=payload.get("guardians"),
        )
        return Response(self.get_serializer(student).data, status=status.HTTP_201_CREATED)

    @resaas_action(detail=True, methods=["get"], label="Who pays", icon="payments",
                   permission="view_student", visible=False)
    def payer(self, request, pk=None):
        person = student_service.payer_person(self.get_object())
        return Response({"person_id": str(person.id), "name": person.full_name})


@registerView("guardians")
class GuardianAPIView(UniqueConflictMixin, BaseAPIView):
    queryset = m.Guardian.objects.select_related("person", "student__person")
    serializer_class = s.GuardianSerializer
    cross_branch_actions = ["list", "retrieve"]

    def perform_create(self, serializer):
        data = serializer.validated_data
        serializer.instance = student_service.add_guardian(
            request=self.request, student=data["student"], person_id=data["person"].id,
            relationship=data.get("relationship", "other"), pays=data.get("pays", False),
            emergency_contact=data.get("emergency_contact", False), can_pick_up=data.get("can_pick_up", True),
        )

    @transaction.atomic
    def perform_update(self, serializer):
        if serializer.validated_data.get("pays"):   # one paying guardian
            m.Guardian.objects.filter(student=serializer.instance.student, pays=True) \
                .exclude(id=serializer.instance.id).update(pays=False)
        super().perform_update(serializer)


@registerView("enrolments")
class EnrolmentAPIView(UniqueConflictMixin, BaseAPIView):
    queryset = m.Enrolment.objects.select_related("student__person", "academic_year", "grade_level", "class_group")
    serializer_class = s.EnrolmentSerializer

    def perform_create(self, serializer):
        data = serializer.validated_data
        serializer.instance = enrolment_service.enrol(
            request=self.request, student=data["student"], academic_year=data["academic_year"],
            grade_level=data["grade_level"], class_group=data.get("class_group"), enrolled_on=data.get("enrolled_on"),
        )

    def perform_update(self, serializer):
        # the status has its own actions; the class too (capacity) - the rest is fixed once enrolled
        raise ResaasAPIException("An enrolment changes through its actions (status, class).",
                                 code="use_actions", status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

    def _status(self, request, to_status):
        enrolment = enrolment_service.change_status(request=request, enrolment=self.get_object(),
                                                    to_status=to_status, reason=request.data.get("reason", ""))
        return Response(self.get_serializer(enrolment).data)

    @resaas_action(detail=True, methods=["post"], label="Activate", icon="check_circle")
    def activate(self, request, pk=None):
        return self._status(request, m.Enrolment.STATUS_ACTIVE)

    @resaas_action(detail=True, methods=["post"], label="Suspend", icon="pause_circle")
    def suspend(self, request, pk=None):
        return self._status(request, m.Enrolment.STATUS_SUSPENDED)

    @resaas_action(detail=True, methods=["post"], label="Transfer", icon="swap_horiz")
    def transfer(self, request, pk=None):
        return self._status(request, m.Enrolment.STATUS_TRANSFERRED)

    @resaas_action(detail=True, methods=["post"], label="Complete", icon="school")
    def complete(self, request, pk=None):
        return self._status(request, m.Enrolment.STATUS_COMPLETED)

    @resaas_action(detail=True, methods=["post"], label="Cancel enrolment", icon="cancel")
    def cancel(self, request, pk=None):
        return self._status(request, m.Enrolment.STATUS_CANCELLED)

    @resaas_action(detail=True, methods=["post"], label="Change class", icon="groups")
    def change_class(self, request, pk=None):
        class_group = m.ClassGroup.objects.filter(id=request.data.get("class_group"),
                                                  entity_id=request.entity_id).first()
        if class_group is None:
            raise ResaasAPIException("Choose a class.", code="invalid", details={"class_group": ["Choose a class."]})
        enrolment = enrolment_service.change_class(request=request, enrolment=self.get_object(),
                                                   class_group=class_group, reason=request.data.get("reason", ""))
        return Response(self.get_serializer(enrolment).data)

    @resaas_action(detail=True, methods=["get"], label="History", icon="history", permission="view_enrolment",
                   visible=False)
    def history(self, request, pk=None):
        rows = self.get_object().status_changes.select_related("created_by").order_by("created_at")
        return Response(s.EnrolmentStatusChangeSerializer(rows, many=True, context={"request": request}).data)

    @resaas_action(detail=True, methods=["get"], label="Report card", icon="grading", permission="view_enrolment",
                   visible=False)
    def report(self, request, pk=None):
        """?period=<id>: per subject, the weighted average and whether it passes."""
        return Response(grading_service.report(self.get_object(), request.query_params.get("period") or None))

    @resaas_action(detail=True, methods=["post"], label="Charge month", icon="receipt_long")
    def charge_month(self, request, pk=None):
        """{month: "YYYY-MM"} - the monthly fee as a draft sale for whoever pays (once per month)."""
        enrolment = self.get_object()
        if enrolment.status != m.Enrolment.STATUS_ACTIVE:
            raise ResaasAPIException("Only an active enrolment is charged.", code="invalid_transition", status_code=409)
        sale = tuition_service.charge(enrolment, m.TuitionRule.KIND_MONTHLY, request.user, month=request.data.get("month"))
        return Response({"sale_id": str(sale.id) if sale else None, "charged": bool(sale)})
