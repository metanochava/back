# hr/serializers/leave_request.py

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.employee import Employee
from hr.models.leave_request import LeaveRequest
from hr.models.leave_type import LeaveType
from hr.serializers.leave_type import LeaveTypeSerializer


class LeaveRequestSerializer(BaseSerializer):

    employee = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        write_only=True,
    )

    employee_data = serializers.SerializerMethodField()

    leave_type = serializers.PrimaryKeyRelatedField(
        queryset=LeaveType.objects.all(),
        write_only=True,
    )

    leave_type_data = LeaveTypeSerializer(source='leave_type', read_only=True)

    class Meta:
        model = LeaveRequest
        fields = "__all__"
        # Only submit/approve/reject/cancel (LeaveRequestAPIView actions,
        # backed by hr/services/leave_service.py) may change these - the
        # same "workflow via actions, not free PATCH" rule the OTP-gated
        # email/mobile fields on UserSerializer follow elsewhere in this
        # project, and pedido secção 49's explicit requirement.
        extra_kwargs = {
            'status': {'read_only': True},
            'days': {'read_only': True},
            'approved_by': {'read_only': True},
            'approved_at': {'read_only': True},
            'rejection_reason': {'read_only': True},
        }

    def get_employee_data(self, obj):
        return {"id": obj.employee_id, "label": str(obj.employee)}

    def validate(self, attrs):
        attrs = super().validate(attrs)

        # Same pattern as EmployeeSerializer: querysets above are
        # deliberately unscoped so a cross-entity id gets a field-attributed
        # 400 instead of silently 404-ing out of a filtered queryset - the
        # tenant boundary is enforced here.
        request = self.context.get("request")
        entity_id = getattr(request, "entity_id", None) if request else None

        if entity_id:
            for field_name in ("employee", "leave_type"):
                related = attrs.get(field_name)

                if related is not None and str(related.entity_id) != str(entity_id):
                    raise serializers.ValidationError({
                        field_name: "Does not belong to the current entity."
                    })

        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                "end_date": "Cannot be earlier than start_date."
            })

        return attrs
