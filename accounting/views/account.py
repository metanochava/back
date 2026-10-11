from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action

from accounting import services
from accounting.models import Account
from accounting.serializers import AccountSerializer


def _date(request, name):
    value = request.query_params.get(name)
    if not value:
        return None
    parsed = parse_date(value)
    if parsed is None:
        raise ValidationError({name: ["Enter a valid date."]})
    return parsed


@registerView("accounts")
class AccountAPIView(BaseAPIView):
    queryset = Account.objects.select_related("parent")
    serializer_class = AccountSerializer

    def perform_destroy(self, instance):
        if instance.lines.exists() or instance.children.exists():
            from django_resaas.saas.core.exceptions import ConflictError

            raise ConflictError("An account with postings or sub-accounts cannot be deleted.", code="account_in_use")
        super().perform_destroy(instance)

    @resaas_action(
        methods=["get"], detail=False, label="Trial balance", icon="balance",
        tooltip="Debit, credit and balance per account", position="l", order=10,
    )
    def trial_balance(self, request):
        """GET ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD - current Entity only."""
        return Response(services.trial_balance(request.entity_id, _date(request, "date_from"), _date(request, "date_to")))
