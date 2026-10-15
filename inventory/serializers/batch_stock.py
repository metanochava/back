from django_resaas.saas.core.base.serializers import BaseSerializer
from inventory.models.batch_stock import BatchStock


class BatchStockSerializer(BaseSerializer):
    class Meta:
        model = BatchStock
        fields = "__all__"
