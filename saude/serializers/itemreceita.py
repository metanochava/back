# saude/serializers/itemreceita.py
from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.itemreceita import ItemReceita
class ItemReceitaSerializer(BaseSerializer):
    class Meta:
        model = ItemReceita
        fields = "__all__"