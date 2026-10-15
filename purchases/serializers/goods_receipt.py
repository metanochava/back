from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer
from purchases.models import GoodsReceipt


class GoodsReceiptSerializer(BaseSerializer):

    order_number = serializers.CharField(read_only=True)

    class Meta:
        model = GoodsReceipt
        fields = "__all__"
