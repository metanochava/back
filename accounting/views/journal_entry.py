from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action

from accounting import services
from accounting.models import JournalEntry, JournalEntryLine
from accounting.serializers import JournalEntryLineSerializer, JournalEntrySerializer


@registerView("journalentries")
class JournalEntryAPIView(BaseAPIView):
    """Drafts are plain CRUD; posting and reversing are domain actions. A
    posted entry answers 409 to any change or delete."""

    queryset = JournalEntry.objects.select_related("journal").prefetch_related("lines")
    serializer_class = JournalEntrySerializer

    def perform_update(self, serializer):
        services.assert_draft(serializer.instance)
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        services.assert_draft(instance)
        super().perform_destroy(instance)

    @resaas_action(
        methods=["post"], detail=True, label="Post", icon="task_alt", url_path="post",
        tooltip="Validate and post the journal entry (it can no longer be changed)", position="t", order=10,
    )
    def post_entry(self, request, pk=None):
        # not named `post`: that is the HTTP method handler of the view
        entry = services.post_entry(entry=self.get_object(), user=request.user)
        return Response(self.get_serializer(entry).data)

    @resaas_action(
        methods=["post"], detail=True, label="Reverse", icon="undo",
        tooltip="Post an opposite entry that cancels this one", position="t", order=20,
    )
    def reverse(self, request, pk=None):
        date = request.data.get("date")
        parsed = parse_date(date) if date else None
        if date and parsed is None:
            raise ValidationError({"date": ["Enter a valid date."]})
        reversal = services.reverse_entry(
            entry=self.get_object(), user=request.user, date=parsed, description=request.data.get("description") or None
        )
        return Response(self.get_serializer(reversal).data)


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
