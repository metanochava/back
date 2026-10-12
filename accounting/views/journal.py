from django_resaas.saas.core.base.views import BaseAPIView, registerView

from accounting.models import Journal
from accounting.serializers import JournalSerializer


@registerView("journals")
class JournalAPIView(BaseAPIView):
    queryset = Journal.objects.all()
    serializer_class = JournalSerializer
