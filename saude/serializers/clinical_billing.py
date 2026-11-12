from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from django_resaas.saas.core.utils.translate import Translate
from saude.models.clinical_billing import ClinicalBillingRule, ClinicalCharge, ExamMaterialRule, MaterialConsumption


def _catalogued_item(request, product_id):
    """{id, nome, ...} of one of the Entity's catalogued items, or None."""
    from django.apps import apps

    if not apps.is_installed("catalog"):
        return None
    from catalog import services as catalog_services

    return catalog_services.get_product_snapshot(product_id, entity_id=getattr(request, "entity_id", None))


class _CataloguedItemMixin:
    """product_id must be one of the Entity's catalogued items; the item's
    name is returned with the rule (product_label)."""

    def validate_product_id(self, value):
        request = self.context.get("request")
        if _catalogued_item(request, value) is None:
            raise serializers.ValidationError(Translate.tdc(request, "Choose an item of this clinic's catalog."))
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        item = _catalogued_item(self.context.get("request"), instance.product_id)
        data["product_label"] = item["nome"] if item else None
        return data


class ClinicalBillingRuleSerializer(_CataloguedItemMixin, BaseSerializer):
    # what each kind needs - the others must stay empty
    REQUIRED = {
        ClinicalBillingRule.KIND_CONSULTATION: (),
        ClinicalBillingRule.KIND_EXAM: ("exame",),
        ClinicalBillingRule.KIND_MEDICATION: ("medicamento",),
    }
    ALLOWED = {
        ClinicalBillingRule.KIND_CONSULTATION: ("specialty",),
        ClinicalBillingRule.KIND_EXAM: ("exame",),
        ClinicalBillingRule.KIND_MEDICATION: ("medicamento",),
    }

    class Meta:
        model = ClinicalBillingRule
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        value = lambda name: attrs.get(name, getattr(self.instance, name, None))  # noqa: E731
        errors = {}
        for name in self.REQUIRED.get(kind, ()):
            if not value(name):
                errors[name] = [Translate.tdc(request, "This field is required.")]
        for name in ("specialty", "exame", "medicamento"):
            if name not in self.ALLOWED.get(kind, ()) and value(name):
                errors[name] = [Translate.tdc(request, "Not used by this kind of rule.")]
        quantity = value("quantity")
        if quantity is not None and quantity <= 0:
            errors["quantity"] = [Translate.tdc(request, "Enter a quantity above zero.")]
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class ExamMaterialRuleSerializer(_CataloguedItemMixin, BaseSerializer):
    class Meta:
        model = ExamMaterialRule
        fields = "__all__"

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError(Translate.tdc(self.context.get("request"), "Enter a quantity above zero."))
        return value


class ClinicalChargeSerializer(BaseSerializer):
    class Meta:
        model = ClinicalCharge
        fields = "__all__"
        read_only_fields = [f.name for f in ClinicalCharge._meta.fields]


class MaterialConsumptionSerializer(BaseSerializer):
    class Meta:
        model = MaterialConsumption
        fields = "__all__"
        read_only_fields = [f.name for f in MaterialConsumption._meta.fields]
