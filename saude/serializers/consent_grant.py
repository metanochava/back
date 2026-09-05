from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.consent_grant import ConsentGrant


class ConsentGrantSerializer(BaseSerializer):

    class Meta:
        model = ConsentGrant
        fields = "__all__"
