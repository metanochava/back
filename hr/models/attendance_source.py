from django.db import models


class AttendanceSource(models.TextChoices):
    """Where the check-in/check-out came from. Only MANUAL/WEB are
    actually produced today (hr/services/attendance_service.py) - the
    rest exist so the field never needs a migration when a real
    biometric/RFID/mobile integration shows up later (pedido secção 23:
    prepare the architecture, don't build the integrations now)."""

    MANUAL = "manual", "Manual"
    WEB = "web", "Web"
    MOBILE = "mobile", "Mobile"
    BIOMETRIC = "biometric", "Biometric"
    RFID = "rfid", "RFID"
    API = "api", "API"
    EXTERNAL_DEVICE = "external_device", "External Device"
