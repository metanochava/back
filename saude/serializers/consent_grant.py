from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.consent_grant import ConsentGrant


class ConsentGrantSerializer(BaseSerializer):

    class Meta:
        model = ConsentGrant
        fields = "__all__"
