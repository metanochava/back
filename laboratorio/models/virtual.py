from django.db import models
from django.db.models import Q

from django_resaas.saas.core.base.models import BaseModel


class VirtualLab(BaseModel):
    """A virtual laboratory (formerly a Lab Manager "lab"): a group of virtual
    machines (Docker containers, one per student) on a shared network or one
    isolated network per machine. `name` names the Docker resources
    (network "<prefix>-<name>", containers "<name>-<user>"), so it is unique
    on the host, across Entities."""

    MODE_SHARED = "shared"
    MODE_ISOLATED = "isolated"
    MODE_CHOICES = ((MODE_SHARED, "Shared"), (MODE_ISOLATED, "Isolated"))

    name = models.SlugField(max_length=60, help_text="e.g. linux (lowercase, digits, -)")
    description = models.TextField(blank=True, default="")
    network_mode = models.CharField(max_length=8, choices=MODE_CHOICES, default=MODE_SHARED, editable=False)
    network_name = models.CharField(max_length=120, blank=True, default="", editable=False)
    class_group = models.ForeignKey("academica.ClassGroup", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="virtual_labs")
    subject = models.ForeignKey("academica.Subject", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="virtual_labs")
    environment = models.ForeignKey("laboratorio.Environment", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="virtual_labs", help_text="The default image of its machines")

    class Meta:
        verbose_name = "Virtual lab"
        verbose_name_plural = "Virtual labs"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["name"], condition=Q(deleted_at__isnull=True),
                                               name="laboratorio_virtuallab_name_on_host")]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "description"]
        crud = True


class VirtualMachine(BaseModel):
    """A student's virtual machine (formerly a Lab Manager "machine"): a
    Docker container with a persistent home volume, SSH / HTTP / HTTPS on
    ports Docker assigns. The password is never stored: it is shown once
    when the machine is made or the password renewed."""

    STATUS_RUNNING = "running"
    STATUS_STOPPED = "stopped"
    STATUS_MISSING = "missing"
    STATUS_DELETED = "deleted"
    STATUS_CHOICES = ((STATUS_RUNNING, "Running"), (STATUS_STOPPED, "Stopped"), (STATUS_MISSING, "Missing"),
                      (STATUS_DELETED, "Deleted"))

    lab = models.ForeignKey(VirtualLab, on_delete=models.PROTECT, related_name="machines")
    enrolment = models.ForeignKey("academica.Enrolment", null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="virtual_machines")
    username = models.SlugField(max_length=60, help_text="The SSH user, also the container's suffix")
    container_name = models.CharField(max_length=130, editable=False)
    image = models.CharField(max_length=200, editable=False)
    ram = models.CharField(max_length=12, editable=False)
    cpus = models.CharField(max_length=8, editable=False)
    ssh_port = models.PositiveIntegerField(null=True, blank=True, editable=False)
    http_port = models.PositiveIntegerField(null=True, blank=True, editable=False)
    https_port = models.PositiveIntegerField(null=True, blank=True, editable=False)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=STATUS_RUNNING, editable=False)
    volume_name = models.CharField(max_length=160, blank=True, default="", editable=False)
    network_name = models.CharField(max_length=160, blank=True, default="", editable=False)
    synced_at = models.DateTimeField(null=True, blank=True, editable=False)
    removed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Virtual machine"
        verbose_name_plural = "Virtual machines"
        ordering = ["lab__name", "username"]
        constraints = [
            models.UniqueConstraint(fields=["container_name"], condition=Q(removed_at__isnull=True),
                                    name="laboratorio_vm_container_on_host"),
            models.UniqueConstraint(fields=["lab", "enrolment"],
                                    condition=Q(removed_at__isnull=True, enrolment__isnull=False),
                                    name="laboratorio_vm_one_per_student_and_lab"),
        ]

    class RESAAS:
        label_field = "container_name"
        search_fields = ["container_name", "username", "enrolment__student__person__full_name"]
        crud = True
