"""The academic structure and classes: plain CRUD (BaseAPIView, PROTECTED,
per action permission, the Entity / Branch scope of BaseAPIView)."""
from django_resaas.saas.core.base.views import BaseAPIView, registerView

from ensino import models as m
from ensino import serializers as s
from ensino.views._conflict import UniqueConflictMixin


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
_crud("academicyears", m.AcademicYear, s.AcademicYearSerializer)
_crud("academicperiods", m.AcademicPeriod, s.AcademicPeriodSerializer)
_crud("classgroups", m.ClassGroup, s.ClassGroupSerializer)
