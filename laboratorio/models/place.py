from django.db import models
from django.db.models import Q

from django_resaas.saas.core.base.models import BaseModel


class Room(BaseModel):
    """A room of the branch: a classroom or a laboratory. academica's
    timetable keeps a room by id and name (TimetableSlot.room_id / room_name)."""

    KIND_CHOICES = (("classroom", "Classroom"), ("laboratory", "Laboratory"), ("workshop", "Workshop"),
                    ("other", "Other"))

    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default="laboratory")
    capacity = models.PositiveSmallIntegerField(default=30)
    location = models.CharField(max_length=120, blank=True, default="", help_text="Building, floor")
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Room"
        verbose_name_plural = "Rooms"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["branch", "name"], condition=Q(deleted_at__isnull=True),
                                               name="laboratorio_room_name_per_branch")]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "location"]
        crud = True


class Network(BaseModel):
    """A network of a room (or of the branch): range, VLAN, gateway."""

    room = models.ForeignKey(Room, null=True, blank=True, on_delete=models.SET_NULL, related_name="networks")
    name = models.CharField(max_length=80)
    cidr = models.CharField(max_length=43, blank=True, default="", help_text="e.g. 10.10.1.0/24")
    vlan = models.PositiveSmallIntegerField(null=True, blank=True)
    gateway = models.GenericIPAddressField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Network"
        verbose_name_plural = "Networks"
        ordering = ["name"]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "cidr"]
        crud = True


class Workstation(BaseModel):
    """A computer of a room. product_id: the catalogued item it is (optional,
    catalog stays generic); labmanager_ref: its id in the Lab Manager."""

    STATUS_CHOICES = (("available", "Available"), ("maintenance", "Maintenance"), ("retired", "Retired"))

    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="workstations")
    network = models.ForeignKey(Network, null=True, blank=True, on_delete=models.SET_NULL, related_name="workstations")
    code = models.CharField(max_length=30, help_text="e.g. LAB1-PC07")
    hostname = models.CharField(max_length=120, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField(max_length=17, blank=True, default="")
    operating_system = models.CharField(max_length=80, blank=True, default="")
    specs = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="available")
    product_id = models.UUIDField(null=True, blank=True, help_text="The catalogued item")
    labmanager_ref = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        verbose_name = "Workstation"
        verbose_name_plural = "Workstations"
        ordering = ["room", "code"]
        constraints = [models.UniqueConstraint(fields=["branch", "code"], condition=Q(deleted_at__isnull=True),
                                               name="laboratorio_workstation_code_per_branch")]

    class RESAAS:
        label_field = "code"
        search_fields = ["code", "hostname", "ip_address", "room__name"]
        crud = True


class Equipment(BaseModel):
    """Other equipment of a room (projector, kit, microscope...)."""

    STATUS_CHOICES = (("available", "Available"), ("in_use", "In use"), ("maintenance", "Maintenance"),
                      ("retired", "Retired"))

    room = models.ForeignKey(Room, null=True, blank=True, on_delete=models.SET_NULL, related_name="equipment")
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=60, blank=True, default="")
    serial_number = models.CharField(max_length=80, blank=True, default="")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="available")
    product_id = models.UUIDField(null=True, blank=True, help_text="The catalogued item")
    notes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Equipment"
        verbose_name_plural = "Equipment"
        ordering = ["name"]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "serial_number", "kind"]
        crud = True


class Environment(BaseModel):
    """A work environment for practical sessions (software, a container
    image of the Lab Manager)."""

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    image = models.CharField(max_length=200, blank=True, default="", help_text="e.g. a container image")
    labmanager_ref = models.CharField(max_length=120, blank=True, default="")
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Environment"
        verbose_name_plural = "Environments"
        ordering = ["name"]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "image"]
        crud = True
