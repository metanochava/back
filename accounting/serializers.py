from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from accounting.models import Account, FiscalPeriod, Journal, JournalEntry, JournalEntryLine, PostingRule


class AccountSerializer(BaseSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Account
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        node = parent
        while node is not None:
            if self.instance is not None and node.pk == self.instance.pk:
                raise serializers.ValidationError({"parent": ["An account cannot be its own ancestor."]})
            node = node.parent
        return attrs


class JournalSerializer(BaseSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Journal
        fields = "__all__"


class FiscalPeriodSerializer(BaseSerializer):
    class Meta:
        model = FiscalPeriod
        fields = "__all__"
        read_only_fields = ["status", "closed_at", "closed_by"]


class JournalEntrySerializer(BaseSerializer):
    """status, number, posting fields and the event source are written by
    accounting.services only."""

    label = serializers.CharField(read_only=True)
    total_debit = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    total_credit = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = JournalEntry
        fields = "__all__"
        read_only_fields = ["number", "status", "posted_at", "posted_by", "reversal_of", "source_event", "source_id"]


class JournalEntryLineSerializer(BaseSerializer):
    label = serializers.CharField(read_only=True)

    class Meta:
        model = JournalEntryLine
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        debit = attrs.get("debit", getattr(self.instance, "debit", 0)) or 0
        credit = attrs.get("credit", getattr(self.instance, "credit", 0)) or 0
        if debit < 0 or credit < 0:
            raise serializers.ValidationError({"debit": ["Amounts cannot be negative."]})
        if (debit > 0) == (credit > 0):
            raise serializers.ValidationError({"debit": ["Enter either a debit or a credit."]})
        return attrs


class PostingRuleSerializer(BaseSerializer):
    class Meta:
        model = PostingRule
        fields = "__all__"
