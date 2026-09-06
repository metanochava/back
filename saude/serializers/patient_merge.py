from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.patient_merge import PatientMerge


class PatientMergeSerializer(BaseSerializer):

    class Meta:
        model = PatientMerge
        fields = "__all__"
