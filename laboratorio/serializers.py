from rest_framework import serializers

from academica.models import Enrolment
from django_resaas.saas.core.base.serializers import BaseSerializer
from laboratorio import models as m
from laboratorio.services import session_service

RELATIONS = ("room", "network", "class_group", "subject", "teacher", "environment", "session", "enrolment",
             "workstation", "assignment", "lab")


class _TenantSerializer(BaseSerializer):
    """Every related record is of the request's Entity; no automatic unique
    validators (the views answer 409)."""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        entity_id = str(getattr(request, "entity_id", "") or "")
        for key in RELATIONS:
            obj = attrs.get(key)
            if obj is not None and entity_id and str(getattr(obj, "entity_id", entity_id)) != entity_id:
                raise serializers.ValidationError({key: ["Does not belong to the current entity."]})
        return attrs

    def _current(self, attrs, key):
        return attrs.get(key, getattr(self.instance, key, None))


def _meta(model, read_only=(), **extra_kwargs):
    return type("Meta", (), {"model": model, "fields": "__all__", "validators": [], "read_only_fields": list(read_only),
                             "extra_kwargs": extra_kwargs})


class RoomSerializer(_TenantSerializer):
    Meta = _meta(m.Room)


class NetworkSerializer(_TenantSerializer):
    Meta = _meta(m.Network)


class WorkstationSerializer(_TenantSerializer):
    Meta = _meta(m.Workstation)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        network, room = self._current(attrs, "network"), self._current(attrs, "room")
        if network is not None and network.room_id and room is not None and network.room_id != room.id:
            raise serializers.ValidationError({"network": ["The network is of another room."]})
        return attrs


class EquipmentSerializer(_TenantSerializer):
    Meta = _meta(m.Equipment)


class EnvironmentSerializer(_TenantSerializer):
    Meta = _meta(m.Environment)


class LabSessionSerializer(_TenantSerializer):
    """status, started_at and ended_at change only through start / end /
    cancel; a room holds one planned / running session at a time."""

    # teacher: the signed-in teacher when not given (LabSessionAPIView.perform_create)
    Meta = _meta(m.LabSession, ("status", "started_at", "ended_at"), teacher={"required": False})

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is not None and self.instance.status != m.LabSession.STATUS_PLANNED and attrs:
            raise serializers.ValidationError({"status": ["Only a planned session can be changed."]})
        starts, ends = self._current(attrs, "starts_at"), self._current(attrs, "ends_at")
        if starts and ends and ends <= starts:
            raise serializers.ValidationError({"ends_at": ["The end is after the start."]})
        if "room" in attrs or "starts_at" in attrs or "ends_at" in attrs:
            session_service.check_room_free(room=self._current(attrs, "room"), starts_at=starts, ends_at=ends,
                                            exclude_id=getattr(self.instance, "id", None))
        return attrs


class SeatAssignmentSerializer(_TenantSerializer):
    Meta = _meta(m.SeatAssignment)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        session_service.check_seat(session=self._current(attrs, "session"), enrolment=self._current(attrs, "enrolment"),
                                   workstation=self._current(attrs, "workstation"))
        return attrs


class SessionExerciseSerializer(_TenantSerializer):
    Meta = _meta(m.SessionExercise)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        session_service.check_exercise(session=self._current(attrs, "session"),
                                       assignment=self._current(attrs, "assignment"))
        return attrs


class RemoteAccessSerializer(_TenantSerializer):
    """Read-only: an access is opened and ended through its actions."""

    class Meta:
        model = m.RemoteAccessSession
        fields = "__all__"
        read_only_fields = [f.name for f in m.RemoteAccessSession._meta.fields]


class VirtualLabSerializer(_TenantSerializer):
    """name names the Docker network and containers: lowercase, digits and -."""

    Meta = _meta(m.VirtualLab, ("network_mode", "network_name"))

    def validate_name(self, value):
        from laboratorio.services.machine_service import sanitize

        if self.instance is not None and value != self.instance.name:
            raise serializers.ValidationError("A lab's name cannot change (it names its Docker resources).")
        value = sanitize(value)
        if m.VirtualLab.objects.filter(name=value).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise serializers.ValidationError("A lab with this name already exists.")
        return value


class VirtualMachineSerializer(_TenantSerializer):
    """Made through VirtualMachineAPIView.create (Docker); afterwards only
    the student (enrolment) it belongs to can change. Never a password."""

    access = serializers.SerializerMethodField()

    class Meta:
        model = m.VirtualMachine
        fields = "__all__"
        validators = []
        read_only_fields = [f.name for f in m.VirtualMachine._meta.fields if f.name not in ("enrolment",)]

    def get_access(self, vm):
        from laboratorio.services.machine_service import access

        return access(vm)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        enrolment = attrs.get("enrolment")
        if enrolment is not None and self.instance is not None and self.instance.lab.class_group_id \
                and enrolment.class_group_id != self.instance.lab.class_group_id:
            raise serializers.ValidationError({"enrolment": ["The student is not of the lab's class."]})
        return attrs


class VirtualMachineCreateSerializer(serializers.Serializer):
    lab = serializers.PrimaryKeyRelatedField(queryset=m.VirtualLab.objects.all())
    enrolment = serializers.PrimaryKeyRelatedField(queryset=Enrolment.objects.all(),
                                                   required=False, allow_null=True)
    username = serializers.CharField(required=False, allow_blank=True, max_length=60)
    image = serializers.CharField(required=False, allow_blank=True, max_length=200)
    ram = serializers.CharField(required=False, allow_blank=True, max_length=12)
    cpus = serializers.CharField(required=False, allow_blank=True, max_length=8)

    def validate(self, attrs):
        entity_id = str(getattr(self.context.get("request"), "entity_id", "") or "")
        for key in ("lab", "enrolment"):
            obj = attrs.get(key)
            if obj is not None and str(obj.entity_id) != entity_id:
                raise serializers.ValidationError({key: ["Does not belong to the current entity."]})
        if not attrs.get("enrolment") and not attrs.get("username"):
            raise serializers.ValidationError({"username": ["Choose a student or a username."]})
        return attrs
