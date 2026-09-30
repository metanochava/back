from django.db import models
from django_resaas.saas.core.base.models import BaseModel
from django_resaas.saas.core.utils import upload_path


class Shift(BaseModel):
    # =========================
    # 🏷️ CORE
    # =========================
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, null=True, blank=True)

    # =========================
    # ⏰ TIME
    # =========================
    start_time = models.TimeField()
    end_time = models.TimeField()

    break_start = models.TimeField(null=True, blank=True)
    break_end = models.TimeField(null=True, blank=True)

    # =========================
    # 📊 CONFIG
    # =========================
    is_night_shift = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # =========================
    # 🔐 META
    # =========================
    class Meta:
        ordering = ['start_time']
        unique_together = ('entity', 'name')

    # =========================
    # ⚙️ RESAAS
    # =========================
    class RESAAS:
        label_field = "name"
        search_fields = ["name", "code"]
        crud = True
        routes = {
            'list': "list_shift",
            'view': "view_shift",
            'add': "add_shift",
            'change': "change_shift"
        }

    def __str__(self):
        return f"{self.name} ({self.start_time}-{self.end_time})"