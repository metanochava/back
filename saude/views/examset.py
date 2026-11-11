from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from django_resaas.saas.core.base.permissions import isPermited
from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.exceptions import ResaasAPIException
from saude.models.examset import ExamSet
from saude.serializers.examset import ExamSetSerializer

MANAGE_ENTITY = "manage_entity_examset"


@registerView("examsets")
class ExamSetAPIView(BaseAPIView):
    """Named sets of exams of the exam request page (one click adds all).

    PROTECTED (list/add/change/delete_examset). Each user sees the Entity's
    sets (owner empty) and their own; another user's personal set is never
    listed (404). A set of the Entity is created, changed or removed only with
    manage_entity_examset. Entity-wide like the catalogue: cross-branch.
    """

    queryset = ExamSet.objects.prefetch_related("exams")
    serializer_class = ExamSetSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "put", "delete"]
    cross_branch_actions = ["list", "retrieve", "update", "partial_update", "destroy"]

    def get_queryset(self):
        return super().get_queryset().filter(Q(owner__isnull=True) | Q(owner=self.request.user))

    def _require_manage_entity(self):
        if not isPermited(request=self.request, role=MANAGE_ENTITY):
            raise ResaasAPIException("Only who manages the clinic's exam sets may change them.",
                                     code="permission_denied", status_code=status.HTTP_403_FORBIDDEN)

    def perform_create(self, serializer):
        scope = serializer.validated_data.pop("scope", "mine")
        if scope == "entity":
            self._require_manage_entity()
            serializer.validated_data["owner"] = None
        else:
            serializer.validated_data["owner"] = self.request.user
        super().perform_create(serializer)

    def perform_update(self, serializer):
        serializer.validated_data.pop("scope", None)   # the kind of a set never changes
        if serializer.instance.owner_id is None:
            self._require_manage_entity()
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        if instance.owner_id is None:
            self._require_manage_entity()
        super().perform_destroy(instance)

    def list(self, request, *args, **kwargs):
        rows = self.filter_queryset(self.get_queryset())
        return Response(self.get_serializer(rows, many=True).data)
