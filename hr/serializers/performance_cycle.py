# hr/serializers/performance_cycle.py

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.performance_cycle import PerformanceCycle


class PerformanceCycleSerializer(BaseSerializer):

    class Meta:
        model = PerformanceCycle
        fields = "__all__"
