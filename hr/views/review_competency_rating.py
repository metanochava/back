# hr/views/review_competency_rating.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.review_competency_rating import ReviewCompetencyRating
from hr.serializers.review_competency_rating import (
    ReviewCompetencyRatingSerializer,
)


@registerView('reviewcompetencyratings', module='hr')
class ReviewCompetencyRatingAPIView(BaseAPIView):
    queryset = ReviewCompetencyRating.objects.all()
    serializer_class = ReviewCompetencyRatingSerializer
