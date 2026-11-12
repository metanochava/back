"""Compatibility: the catalogue moved to the catalog module (/api/catalog/...).
The old /api/inventory/<resource>/ routes stay for clients that still call
them (same views, same permissions, the inventory module active). New code
uses /api/catalog/. Remove once nothing calls them."""
from django_resaas.saas.core.base.views import registerView

from catalog.views.price_list_item import PriceListItemAPIView
from catalog.views.pricelist import PriceListAPIView
from catalog.views.product import ProductAPIView
from catalog.views.productcategory import ProductCategoryAPIView
from catalog.views.productmedia import ProductMediaAPIView


@registerView("products", module="inventory")
class LegacyProductAPIView(ProductAPIView):
    pass


@registerView("productcategorys", module="inventory")
class LegacyProductCategoryAPIView(ProductCategoryAPIView):
    pass


@registerView("productmedias", module="inventory")
class LegacyProductMediaAPIView(ProductMediaAPIView):
    pass


@registerView("pricelists", module="inventory")
class LegacyPriceListAPIView(PriceListAPIView):
    pass


@registerView("pricelistitems", module="inventory")
class LegacyPriceListItemAPIView(PriceListItemAPIView):
    pass
