from django.db import models
from django.db.models import Q
from django_resaas.saas.core.base.models import BaseModel


class FavouriteExam(BaseModel):
    """An exam on the Entity's quick list of the exam request.

    The list is shared by everyone in the Entity, whatever the branch (the
    exam catalogue is Entity-wide too); `branch` only records where it was
    added. Removing it is a soft delete, so a live row is unique per exam.
    """

    exame = models.ForeignKey(
        "saude.ExameMedico",
        on_delete=models.CASCADE,
        related_name="favourites",
    )

    class Meta:
        verbose_name = "Favourite Exam"
        verbose_name_plural = "Favourite Exams"
        ordering = ["exame__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "exame"],
                condition=Q(deleted_at__isnull=True),
                name="saude_favouriteexam_unique_live",
            ),
        ]

    class RESAAS:
        label_field = "exame"
        search_fields = ["exame__nome", "exame__codigo"]
        crud = False

    def __str__(self):
        return str(self.exame)
