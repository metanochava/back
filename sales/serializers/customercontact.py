from django_resaas.saas.core.base.serializers import BaseSerializer
from sales.models.customercontact import CustomerContact


class CustomerContactSerializer(BaseSerializer):

    class Meta:
        model = CustomerContact
        fields = "__all__"
