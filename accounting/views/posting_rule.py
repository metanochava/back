from django_resaas.saas.core.base.views import BaseAPIView, registerView

from accounting.models import PostingRule
from accounting.serializers import PostingRuleSerializer


@registerView("postingrules")
class PostingRuleAPIView(BaseAPIView):
    queryset = PostingRule.objects.select_related("journal", "debit_account", "credit_account")
    serializer_class = PostingRuleSerializer
