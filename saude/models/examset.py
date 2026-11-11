from django.conf import settings
from django.db import models
from django.db.models import Q
from django_resaas.saas.core.base.models import BaseModel


class ExamSet(BaseModel):
    """A named set of exams added to an exam request in one click (e.g.
    "Pre-operative", "Diabetes follow-up").

    Two kinds, both of the Entity (whatever the branch, like the catalogue):

    - the Entity's: `owner` empty, for everyone; kept by whoever has
      manage_entity_examset;
    - personal: `owner` = the user who created it, seen and kept only by them.

    `owner` is set by the server from the scope asked (never from the client).
    Removing is a soft delete, so a live name is unique per owner.
    """

    name = models.CharField(max_length=120)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="exam_sets",
        editable=False,
    )

    exams = models.ManyToManyField("saude.ExameMedico", related_name="exam_sets", blank=True)

    class Meta:
        verbose_name = "Exam Set"
        verbose_name_plural = "Exam Sets"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "owner", "name"],
                condition=Q(deleted_at__isnull=True, owner__isnull=False),
                name="saude_examset_unique_personal_name",
            ),
            models.UniqueConstraint(
                fields=["entity", "name"],
                condition=Q(deleted_at__isnull=True, owner__isnull=True),
                name="saude_examset_unique_entity_name",
            ),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name"]
        crud = False

    def __str__(self):
        return self.name
