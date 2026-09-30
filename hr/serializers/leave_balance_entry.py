# hr/serializers/leave_balance_entry.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.employee import Employee
from hr.models.leave_balance_entry import LeaveBalanceEntry, LeaveBalanceEntryType
from hr.models.leave_type import LeaveType

# entry_type values a caller may set directly through this API. `usage`
# and `expiry` are ledger-integrity-critical - they must only ever come
# from leave_service.approve()/cancel(), never a free-form POST here (a
# manual "usage" row wouldn't be tied to a real LeaveRequest, breaking the
# audit trail pedido secção 26 asks for). `allocation`/`adjustment` (e.g.
# HR granting the yearly days, or a manual correction) are legitimately
# manual and stay open.
DIRECTLY_CREATABLE_ENTRY_TYPES = {
    LeaveBalanceEntryType.ALLOCATION,
    LeaveBalanceEntryType.ADJUSTMENT,
}


class LeaveBalanceEntrySerializer(BaseSerializer):

    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    employee_data = serializers.SerializerMethodField()

    leave_type = serializers.PrimaryKeyRelatedField(queryset=LeaveType.objects.all())
    leave_type_data = serializers.SerializerMethodField()

    class Meta:
        model = LeaveBalanceEntry
        fields = "__all__"
        # Service-created entries (usage/adjustment-on-cancel) always set
        # `reference` themselves; a directly-created row never has one.
        extra_kwargs = {
            'reference': {'read_only': True},
        }

    def get_employee_data(self, obj):
        return {"id": obj.employee_id, "label": str(obj.employee)}

    def get_leave_type_data(self, obj):
        return {"id": obj.leave_type_id, "label": str(obj.leave_type)}

    def validate(self, attrs):
        attrs = super().validate(attrs)

        entry_type = attrs.get("entry_type")

        if entry_type is not None and entry_type not in DIRECTLY_CREATABLE_ENTRY_TYPES:
            raise serializers.ValidationError({
                "entry_type": (
                    "'usage' and 'expiry' entries are created automatically "
                    "by the leave approval workflow, not directly."
                )
            })

        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None

        if entity_id:
            for field_name in ("employee", "leave_type"):
                related = attrs.get(field_name)

                if related is not None and str(related.entity_id) != str(entity_id):
                    raise serializers.ValidationError({
                        field_name: "Does not belong to the current entity."
                    })

        return attrs
