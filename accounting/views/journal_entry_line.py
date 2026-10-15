from rest_framework.exceptions import ValidationError
from django_resaas.saas.core.base.views import BaseAPIView, registerView
from accounting import services
from accounting.models import JournalEntryLine
from accounting.serializers import JournalEntryLineSerializer


@registerView("journalentrylines")
class JournalEntryLineAPIView(BaseAPIView):
    queryset = JournalEntryLine.objects.select_related("account", "entry")
    serializer_class = JournalEntryLineSerializer

    def perform_create(self, serializer):
        services.assert_draft(serializer.validated_data["entry"])
        super().perform_create(serializer)

    def perform_update(self, serializer):
        services.assert_draft(serializer.instance.entry)
        entry = serializer.validated_data.get("entry")
        if entry is not None and entry != serializer.instance.entry:
            raise ValidationError({"entry": ["A line cannot be moved to another journal entry."]})
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        services.assert_draft(instance.entry)
        super().perform_destroy(instance)
