# hr/serializers/specialty.py

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.specialty import Specialty


class SpecialtySerializer(BaseSerializer):

    class Meta:
        model = Specialty
        fields = "__all__"