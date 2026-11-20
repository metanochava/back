from django.conf import settings
from django.db import models
from django.db.models import Q

from django_resaas.saas.core.base.models import BaseModel


class PrepStation(BaseModel):
    """Where ordered items are prepared: the kitchen, the bar. Its catalogue
    categories (ids of catalog categories - catalog stays generic) decide
    which items reach its screen; an item of no station's category is served
    without a ticket."""

    name = models.CharField(max_length=60)
    category_ids = models.JSONField(default=list, blank=True,
                                    help_text="The catalogue categories prepared here")
    order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Preparation station"
        verbose_name_plural = "Preparation stations"
        ordering = ["order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "name"], name="unique_prep_station_name_per_branch"),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name"]
        crud = True
        routes = {"list": "list_prepstation"}

    def __str__(self):
        return self.name


class PrepTicket(BaseModel):
    """What a station has to prepare for one tab: new -> preparing -> ready
    -> served (new -> ready is allowed). Orders on the tab join its NEW
    ticket; once the station starts it, the next orders make a new ticket."""

    STATUS_NEW = "new"
    STATUS_PREPARING = "preparing"
    STATUS_READY = "ready"
    STATUS_SERVED = "served"
    STATUS_CHOICES = ((STATUS_NEW, "New"), (STATUS_PREPARING, "Preparing"), (STATUS_READY, "Ready"),
                      (STATUS_SERVED, "Served"))
    TRANSITIONS = {
        STATUS_NEW: {STATUS_PREPARING, STATUS_READY},
        STATUS_PREPARING: {STATUS_READY},
        STATUS_READY: {STATUS_SERVED},
        STATUS_SERVED: set(),
    }

    station = models.ForeignKey("hospitality.PrepStation", on_delete=models.PROTECT, related_name="tickets")
    sale_id = models.UUIDField()
    table = models.ForeignKey("hospitality.DiningTable", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="tickets")
    tab_label = models.CharField(max_length=60, blank=True, default="")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_NEW)
    started_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    served_at = models.DateTimeField(null=True, blank=True)
    served_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="+")

    class Meta:
        verbose_name = "Preparation ticket"
        verbose_name_plural = "Preparation tickets"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["station", "sale_id"], condition=Q(status="new"),
                                    name="one_new_prep_ticket_per_station_and_tab"),
        ]

    class RESAAS:
        label_field = "tab_label"
        search_fields = ["tab_label"]
        crud = False
        routes = {"list": "list_prepticket"}


class PrepTicketLine(BaseModel):
    ticket = models.ForeignKey("hospitality.PrepTicket", on_delete=models.CASCADE, related_name="lines")
    product_id = models.UUIDField()
    product_nome = models.CharField(max_length=255)
    quantidade = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        verbose_name = "Preparation ticket line"
        verbose_name_plural = "Preparation ticket lines"
        ordering = ["created_at"]

    class RESAAS:
        label_field = "product_nome"
        crud = False
