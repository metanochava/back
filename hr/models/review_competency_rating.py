# hr/models/review_competency_rating.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from django_resaas.saas.core.base.models import BaseModel


class ReviewCompetencyRating(BaseModel):
    """Links a PerformanceReview to a Competency with a rating - lets one
    review score several competencies instead of one giant free-text
    field (pedido secção 32/34)."""

    review = models.ForeignKey(
        'hr.PerformanceReview',
        on_delete=models.CASCADE,
        related_name='competency_ratings',
    )

    competency = models.ForeignKey(
        'hr.Competency',
        on_delete=models.CASCADE,
        related_name='+',
    )

    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )

    comments = models.TextField(blank=True)

    class Meta:
        ordering = ['review', 'competency']
        unique_together = (('review', 'competency'),)

    class RESAAS:
        label_field = "id"
        search_fields = ["review__id", "competency__name"]
        crud = True

    def __str__(self):
        return f"{self.review} - {self.competency}: {self.rating}"
