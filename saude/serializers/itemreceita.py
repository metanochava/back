# saude/serializers/itemreceita.py
from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.itemreceita import ItemReceita
class ItemReceitaSerializer(BaseSerializer):
    class Meta:
        model = ItemReceita
        fields = "__all__"