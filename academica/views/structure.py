"""The academic structure and classes: plain CRUD (BaseAPIView, PROTECTED,
per action permission, the Entity / Branch scope of BaseAPIView)."""
from django_resaas.saas.core.base.views import BaseAPIView, registerView

from academica import models as m
from academica import serializers as s
from academica.views._conflict import UniqueConflictMixin
from rest_framework.response import Response

from django_resaas.saas.core.decorators.action import resaas_action
from django_resaas.saas.core.exceptions import ResaasAPIException
from django_resaas.saas.core.utils import PDF

from academica.services import documents_service, progression_service


def _crud(name, model, serializer, **extra):
    view = type(f"{model.__name__}APIView", (UniqueConflictMixin, BaseAPIView), {
        "queryset": model.objects.all(), "serializer_class": serializer, "__module__": __name__, **extra,
    })
    return registerView(name)(view)


# the structure is the Entity's (every branch reads it)
STRUCTURE_SCOPE = {"cross_branch_actions": ["list", "retrieve"]}

_crud("gradingscales", m.GradingScale, s.GradingScaleSerializer, **STRUCTURE_SCOPE)
_crud("educationlevels", m.EducationLevel, s.EducationLevelSerializer, **STRUCTURE_SCOPE)
_crud("programmes", m.Programme, s.ProgrammeSerializer, **STRUCTURE_SCOPE)
_crud("gradelevels", m.GradeLevel, s.GradeLevelSerializer, **STRUCTURE_SCOPE)
_crud("subjects", m.Subject, s.SubjectSerializer, **STRUCTURE_SCOPE)
_crud("curriculumitems", m.CurriculumItem, s.CurriculumItemSerializer, **STRUCTURE_SCOPE)
_crud("academicperiods", m.AcademicPeriod, s.AcademicPeriodSerializer)


@registerView("academicyears")
class AcademicYearAPIView(UniqueConflictMixin, BaseAPIView):
    """Plus closing the year (progression_service): every active enrolment
    gets its result and is completed; the next year's enrolments follow."""

    queryset = m.AcademicYear.objects.all()
    serializer_class = s.AcademicYearSerializer

    def _next_year(self, request, value):
        if not value:
            return None
        year = m.AcademicYear.objects.filter(id=value, entity_id=request.entity_id).first() if _uuid(value) else None
        if year is None:
            raise ResaasAPIException("Choose a later academic year of this school.", code="invalid",
                                     details={"next_year": ["Choose a later academic year of this school."]})
        return year

    @resaas_action(detail=True, methods=["get"], label="Year-end preview", icon="preview",
                   permission="close_year_academicyear", visible=False)
    def progression(self, request, pk=None):
        """?next_year=<id>: what closing the year would do (nothing written)."""
        return Response(progression_service.preview(self.get_object(),
                                                    self._next_year(request, request.query_params.get("next_year"))))

    @resaas_action(detail=True, methods=["post"], label="Close the year", icon="event_available")
    def close_year(self, request, pk=None):
        """{next_year?}: results, completions, the next year's enrolments; the year closes."""
        return Response(progression_service.close_year(
            request=request, academic_year=self.get_object(),
            next_year=self._next_year(request, request.data.get("next_year")),
        ))


@registerView("classgroups")
class ClassGroupAPIView(UniqueConflictMixin, BaseAPIView):
    queryset = m.ClassGroup.objects.all()
    serializer_class = s.ClassGroupSerializer

    @resaas_action(detail=True, methods=["get"], label="Grade sheet (PDF)", icon="picture_as_pdf",
                   permission="view_classgroup")
    def sheet_pdf(self, request, pk=None):
        """?period=<id>: the class's grade sheet (pauta) as a PDF."""
        class_group = self.get_object()
        period = None
        if request.query_params.get("period"):
            period = m.AcademicPeriod.objects.filter(id=request.query_params["period"], entity_id=request.entity_id).first()
        return PDF("academica/pdf/class_sheet.html", request,
                   **documents_service.class_sheet(request, class_group, class_group.academic_year, period))


def _uuid(value):
    import uuid

    try:
        uuid.UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False
