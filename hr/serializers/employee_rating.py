# hr/serializers/employee_rating.py

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.employee_rating import EmployeeRating


class EmployeeRatingSerializer(BaseSerializer):
    """Read only (ratings are made by the rated service's module through
    hr/services/employee_rating_service.rate). The rater is never exposed."""

    class Meta:
        model = EmployeeRating
        exclude = ["rated_by"]
        read_only_fields = [f.name for f in EmployeeRating._meta.fields]
