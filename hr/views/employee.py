# hr/views/employee.py

import json

from django.db import transaction
from rest_framework.response import Response
from rest_framework import status

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action
from django_resaas.saas.core.base.permissions import isPermited
from django_resaas.saas.core.utils.translate import Translate
from django_resaas.saas.models.entity import Entity

from django_resaas.saas.models.branch import Branch

from hr.models.employee import Employee
from hr.models.job_position import JobPosition
from hr.models.job_grade import JobGrade
from hr.models.department import Department
from hr.models.attendance import AttendanceSource
from hr.models.onboarding_template import OnboardingTemplate
from hr.serializers.employee import EmployeeSerializer
from hr.serializers.attendance import AttendanceSerializer
from hr.serializers.employee_onboarding import EmployeeOnboardingSerializer
from hr.serializers.promotion import PromotionSerializer
from hr.serializers.transfer import TransferSerializer
from hr.serializers.termination import TerminationSerializer
from hr.serializers.employee_offboarding import EmployeeOffboardingSerializer
from hr.services.employee_number_service import EmployeeNumberService
from hr.services import attendance_service
from hr.services import onboarding_service
from hr.services import lifecycle_service
from hr.services.employee_registration_service import (
    register_employee,
    EmployeeRegistrationError,
    EmployeeAlreadyExists,
)

# Fase 9 (Employee Lifecycle): once created, these fields only change
# through apply_promotion/apply_transfer below - never a free PATCH -
# because changing them needs to also write the Promotion/Transfer
# history row in the same transaction (pedido secção 17). `branch`/
# `entity` are already forced read-only for every model by
# BaseSerializer.DEFAULT_READ_ONLY_FIELDS; position/job_grade are not,
# since EmployeeSerializer must still accept them at creation time
# (e.g. recruitment_service.hire()).
LOCKED_ON_UPDATE_FIELDS = {"position", "job_grade"}


@registerView('employees', module='hr')
class EmployeeAPIView(BaseAPIView):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer

    def perform_create(self, serializer):
        data = {
            "created_by": self.request.user,
            "updated_by": self.request.user,
            "entity_id": self.request.entity_id,
            "branch_id": self.request.branch_id,
        }

        with transaction.atomic():
            if not serializer.validated_data.get("code"):
                entity = Entity.objects.get(id=self.request.entity_id)
                data["code"] = EmployeeNumberService.generate(entity)

            serializer.save(**data)

    def update(self, request, *args, **kwargs):
        locked_present = LOCKED_ON_UPDATE_FIELDS.intersection(request.data.keys())

        if locked_present:
            return Response(
                {
                    "detail": (
                        f"{', '.join(sorted(locked_present))} can only be "
                        "changed via apply_promotion/apply_transfer."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().update(request, *args, **kwargs)

    # =========================
    # REGISTRATION (add_employee)
    # =========================
    # Person(+reuse)/Document/PersonContact/Employee, all in one DB
    # transaction (employee_registration_service.register_employee) -
    # see EmployeeSEPage.vue for the full flow (validate -> match ->
    # confirm -> register). multipart/form-data because a new Person's
    # photo and each Document's own file can't ride inside a single
    # JSON body; BaseStore's generic FormData builder only flattens
    # plain scalars/arrays (see base_store.js), not this shape (a
    # nested, per-item list of files) - so this one compound action
    # builds its own request body instead of stretching that generic
    # mechanism to fit a shape it was never meant for.
    @resaas_action(detail=False, methods=["post"])
    def register(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.data.get("payload") or "{}")
        except (TypeError, ValueError):
            return Response(
                {"detail": Translate.tdc(request, "Invalid payload.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        person_id = payload.get("person_id") or None

        # add_employee is already required for this action itself (its
        # own default codename, register_employee - see
        # BaseAPIView.get_action_permission()); these are the ADDITIONAL
        # capabilities the specific payload actually exercises, checked
        # individually so a role only needs add_document/add_personcontact
        # when it is genuinely asking to create one (CLAUDE.md: don't
        # allow creating Document/PersonContact/Person without the
        # matching permission, even from inside a compound action).
        required_extra = []

        if not person_id:
            required_extra.append("add_person")
        if payload.get("documents"):
            required_extra.append("add_document")
        if payload.get("contacts"):
            required_extra.append("add_personcontact")

        missing = [p for p in required_extra if not isPermited(request=request, role=p)]

        if missing:
            return Response(
                {"detail": f"{Translate.tdc(request, 'Missing permission(s)')}: {', '.join(missing)}."},
                status=status.HTTP_403_FORBIDDEN,
            )

        documents = []
        for index, doc in enumerate(payload.get("documents") or []):
            file_key = doc.get("_file_key")
            documents.append({
                **doc,
                "arquivo": request.FILES.get(file_key) if file_key else None,
            })

        try:
            employee = register_employee(
                request=request,
                person_id=person_id,
                person_data=payload.get("person"),
                photo=request.FILES.get("person_photo"),
                documents=documents,
                contacts=payload.get("contacts"),
                employee_data=payload.get("employee") or {},
            )
        except EmployeeAlreadyExists as exc:
            return Response(
                {
                    "detail": Translate.tdc(request, "This person is already an employee in this branch."),
                    "existing_employee_id": str(exc.employee.id),
                },
                status=status.HTTP_409_CONFLICT,
            )
        except EmployeeRegistrationError as exc:
            return Response(exc.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            EmployeeSerializer(employee, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    # =========================
    # ATTENDANCE
    # =========================
    # get_object() already scopes to the caller's tenant (get_queryset()
    # filters by entity_id/branch_id - see BaseAPIView), so an Entity
    # can never check-in/check-out an Employee it can't already see.

    @resaas_action(detail=True, methods=["post"])
    def check_in(self, request, *args, **kwargs):
        employee = self.get_object()
        source = request.data.get("source") or AttendanceSource.MANUAL

        try:
            with transaction.atomic():
                attendance = attendance_service.check_in(
                    employee, source=source, actor=request.user
                )
        except attendance_service.AttendanceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            AttendanceSerializer(attendance, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @resaas_action(detail=True, methods=["post"])
    def check_out(self, request, *args, **kwargs):
        employee = self.get_object()

        try:
            with transaction.atomic():
                attendance = attendance_service.check_out(
                    employee, actor=request.user
                )
        except attendance_service.AttendanceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            AttendanceSerializer(attendance, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    # =========================
    # ONBOARDING
    # =========================

    @resaas_action(detail=True, methods=["post"])
    def start_onboarding(self, request, *args, **kwargs):
        employee = self.get_object()

        template = None
        template_id = request.data.get("template")

        if template_id:
            try:
                template = OnboardingTemplate.objects.get(
                    id=template_id, entity_id=employee.entity_id,
                )
            except OnboardingTemplate.DoesNotExist:
                return Response(
                    {"detail": "Onboarding template not found for this entity."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            with transaction.atomic():
                onboarding = onboarding_service.start_onboarding(
                    employee, template=template, actor=request.user
                )
        except onboarding_service.OnboardingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            EmployeeOnboardingSerializer(onboarding, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    # =========================
    # LIFECYCLE (Fase 9)
    # =========================

    @resaas_action(detail=True, methods=["post"])
    def apply_promotion(self, request, *args, **kwargs):
        employee = self.get_object()

        try:
            new_position = JobPosition.objects.get(
                id=request.data.get("new_position"), entity_id=employee.entity_id,
            )
        except (JobPosition.DoesNotExist, ValueError, TypeError):
            return Response(
                {"detail": "new_position not found for this entity."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_job_grade = None
        new_job_grade_id = request.data.get("new_job_grade")
        if new_job_grade_id:
            try:
                new_job_grade = JobGrade.objects.get(
                    id=new_job_grade_id, entity_id=employee.entity_id,
                )
            except (JobGrade.DoesNotExist, ValueError, TypeError):
                return Response(
                    {"detail": "new_job_grade not found for this entity."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        effective_date = request.data.get("effective_date")
        if not effective_date:
            return Response(
                {"detail": "effective_date is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                promotion = lifecycle_service.apply_promotion(
                    employee,
                    new_position=new_position,
                    new_job_grade=new_job_grade,
                    effective_date=effective_date,
                    reason=request.data.get("reason", ""),
                    approved_by=request.user,
                    actor=request.user,
                )
        except lifecycle_service.LifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            PromotionSerializer(promotion, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @resaas_action(detail=True, methods=["post"])
    def apply_transfer(self, request, *args, **kwargs):
        employee = self.get_object()

        try:
            to_branch = Branch.objects.get(id=request.data.get("to_branch"))
        except (Branch.DoesNotExist, ValueError, TypeError):
            return Response(
                {"detail": "to_branch not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        to_department = None
        to_department_id = request.data.get("to_department")
        if to_department_id:
            try:
                to_department = Department.objects.get(id=to_department_id)
            except (Department.DoesNotExist, ValueError, TypeError):
                return Response(
                    {"detail": "to_department not found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        to_position = None
        to_position_id = request.data.get("to_position")
        if to_position_id:
            try:
                to_position = JobPosition.objects.get(id=to_position_id)
            except (JobPosition.DoesNotExist, ValueError, TypeError):
                return Response(
                    {"detail": "to_position not found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        effective_date = request.data.get("effective_date")
        if not effective_date:
            return Response(
                {"detail": "effective_date is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                transfer = lifecycle_service.apply_transfer(
                    employee,
                    to_branch=to_branch,
                    to_department=to_department,
                    to_position=to_position,
                    effective_date=effective_date,
                    reason=request.data.get("reason", ""),
                    approved_by=request.user,
                    actor=request.user,
                )
        except lifecycle_service.LifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            TransferSerializer(transfer, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @resaas_action(detail=True, methods=["post"])
    def terminate_employee(self, request, *args, **kwargs):
        employee = self.get_object()

        termination_type = request.data.get("termination_type")
        termination_date = request.data.get("termination_date")

        if not termination_type or not termination_date:
            return Response(
                {"detail": "termination_type and termination_date are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                termination = lifecycle_service.terminate_employee(
                    employee,
                    termination_type=termination_type,
                    termination_date=termination_date,
                    reason=request.data.get("reason", ""),
                    initiated_by=request.user,
                    actor=request.user,
                )
        except lifecycle_service.LifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            TerminationSerializer(termination, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @resaas_action(detail=True, methods=["post"])
    def start_offboarding(self, request, *args, **kwargs):
        employee = self.get_object()

        try:
            with transaction.atomic():
                offboarding = lifecycle_service.start_offboarding(
                    employee, actor=request.user,
                )
        except lifecycle_service.LifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            EmployeeOffboardingSerializer(offboarding, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    # =========================
    # REPORTS (Fase 10)
    # =========================
    # Reusa a acao generica pdflist() de BaseAPIView - so enriquece o
    # contexto (headcount por departamento) para hr/employee_list.html.

    def get_pdflist_context(self, request, queryset):
        context = super().get_pdflist_context(request, queryset)

        by_department = {}
        for employee in queryset.select_related("position__department"):
            department = employee.position.department if employee.position else None
            name = department.name if department else "No Department"
            by_department[name] = by_department.get(name, 0) + 1

        context["section_title"] = "Headcount Report"
        context["headcount_by_department"] = sorted(
            by_department.items(), key=lambda item: item[1], reverse=True
        )

        return context
