from django.db import models
from django.db.models import Q
from django_resaas.saas.core.base.models import BaseModel


class Stage(BaseModel):
    """A stage of the Entity's sales pipeline. Moving an opportunity to a
    stage marked is_won / is_lost closes it (crm.services.move_opportunity)."""

    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    probability = models.PositiveSmallIntegerField(default=0, help_text="Chance of winning, 0-100 %")
    is_won = models.BooleanField(default=False)
    is_lost = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Stage"
        verbose_name_plural = "Stages"
        ordering = ["order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "name"], name="unique_crm_stage_name_per_entity"),
            models.CheckConstraint(condition=Q(probability__lte=100), name="crm_stage_probability_max_100"),
            models.CheckConstraint(condition=~Q(is_won=True, is_lost=True), name="crm_stage_not_won_and_lost"),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name"]
        crud = True
        routes = {"list": "list_stage"}

    def __str__(self):
        return self.name
