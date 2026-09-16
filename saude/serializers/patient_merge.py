from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.patient_merge import PatientMerge


class PatientMergeSerializer(BaseSerializer):

    class Meta:
        model = PatientMerge
        fields = "__all__"
