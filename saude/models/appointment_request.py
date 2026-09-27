from django.conf import settings
from django.db import models
from django.db.models import Q

from django_resaas.saas.core.base.models import BaseModel


class AppointmentRequest(BaseModel):
    """An appointment asked for on the clinic's public site.

    A visitor is not a patient, and Agenda needs one, so the booking is a
    request that holds the slot: staff confirm it - choosing or registering
    the patient, which creates the Agenda - or reject it
    (saude/services/public_booking_service.py). Entity comes from the site
    (request Origin), Branch from the doctor's schedule (HorarioMedico) the
    slot belongs to.
    """

    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_REJECTED, "Rejected"),
    ]

    medico = models.ForeignKey(
        "hr.Employee",
        on_delete=models.CASCADE,
        related_name="appointment_requests",
    )
    data = models.DateField()
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()

    # what the visitor typed (read only for staff)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30)
    email = models.EmailField(null=True, blank=True)
    specialty = models.CharField(max_length=150, null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    site = models.CharField(max_length=255, editable=False)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    agenda = models.OneToOneField(
        "saude.Agenda",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="appointment_request",
        editable=False,
    )
    rejection_reason = models.TextField(null=True, blank=True, editable=False)
    handled_at = models.DateTimeField(null=True, blank=True, editable=False)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="handled_appointment_requests",
        editable=False,
    )

    class Meta:
        verbose_name = "Appointment request"
        verbose_name_plural = "Appointment requests"
        ordering = ["data", "hora_inicio"]
        constraints = [
            # one pending request per doctor and start time: two visitors
            # cannot both hold the same slot (the database decides the race)
            models.UniqueConstraint(
                fields=["medico", "data", "hora_inicio"],
                condition=Q(status="pending", deleted_at__isnull=True),
                name="saude_appointment_request_one_pending_per_slot",
            ),
        ]
        indexes = [models.Index(fields=["entity", "status", "data"])]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "phone", "email", "medico__person__full_name"]
        crud = True

    def __str__(self):
        return f"{self.name} - {self.data} {self.hora_inicio}"
