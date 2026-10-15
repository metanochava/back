from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer
from purchases.models import GoodsReceiptLine


class GoodsReceiptLineSerializer(BaseSerializer):

    label = serializers.CharField(read_only=True)

    class Meta:
        model = GoodsReceiptLine
        fields = "__all__"
