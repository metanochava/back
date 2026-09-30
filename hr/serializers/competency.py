# hr/serializers/competency.py

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.competency import Competency


class CompetencySerializer(BaseSerializer):

    class Meta:
        model = Competency
        fields = "__all__"
