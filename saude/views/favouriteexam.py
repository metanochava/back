from django_resaas.saas.core.base.views import BaseAPIView
from django_resaas.saas.core.base.views import registerView
from saude.models.favouriteexam import FavouriteExam
from saude.serializers.favouriteexam import FavouriteExamSerializer


@registerView("favouriteexams")
class FavouriteExamAPIView(BaseAPIView):
    """The Entity's quick list of exams on the exam request page.

    Shared by the whole Entity: reading and removing are cross-branch
    (Entity scope still applies); adding records the current branch.
    Bounded by the catalogue, so it is not paginated.
    """

    queryset = FavouriteExam.objects.select_related("exame")
    serializer_class = FavouriteExamSerializer
    pagination_class = None
    http_method_names = ["get", "post", "delete"]
    cross_branch_actions = ["list", "retrieve", "destroy"]
