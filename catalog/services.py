"""Public services of the catalog (horizontal): what an Entity sells or buys.

Other modules (inventory, sales, purchases, farmacia, saude, ...) read the
catalogue through these functions and keep loose product ids - never
catalog.models. Nothing here knows about stock, sales or any vertical.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from catalog.models import PriceList, PriceListItem, Product


def catalog_module_active(entity_id):
    """catalog is installed (it is) and active for the Entity."""
    from django_resaas.saas.models.entity_app import EntityApp

    return EntityApp.objects.filter(entity_id=entity_id, app__name="catalog", state="Active").exists()


def is_stockable(product):
    """Goods hold stock; a service never does, nor does a product with
    variants (its variants hold it). The catalogue decides what CAN hold
    stock; inventory keeps it."""
    if product.product_type == Product.TYPE_SERVICE:
        return False
    return not product.variants.exists()


def get_price(product_id, entity_id, price_list_id=None, quantity=1, date=None):
    """{"price", "price_list"} of one of the Entity's products: the list's
    price for the highest min_quantity <= quantity when the list is active and
    valid on `date`, else Product.preco_base (price_list None). None for an
    unknown product."""

    try:
        product = Product.objects.filter(id=product_id, entity_id=entity_id).first()
    except (ValueError, ValidationError):
        product = None
    if product is None:
        return None

    date = date or timezone.localdate()
    if price_list_id and get_price_list_snapshot(price_list_id, entity_id):
        price_list = (
            PriceList.objects.filter(id=price_list_id, entity_id=entity_id, active=True)
            .filter(Q(valid_from__isnull=True) | Q(valid_from__lte=date))
            .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=date))
            .first()
        )
        if price_list is not None:
            item = (
                PriceListItem.objects.filter(price_list=price_list, product=product, min_quantity__lte=Decimal(quantity))
                .order_by("-min_quantity")
                .first()
            )
            if item is not None:
                return {"price": item.price, "price_list": str(price_list.id)}

    return {"price": product.preco_base, "price_list": None}


def get_prices(product_ids, entity_id, price_list_id=None, date=None):
    """get_price() for several of the Entity's products at once (quantity 1),
    in a fixed number of queries: {product_id: {"price", "price_list",
    "ativo"}}. Same rule: the list's price when the list is active and valid
    on `date` and has the product, else Product.preco_base. Unknown products,
    or another Entity's, are left out."""

    products = {
        row["id"]: row
        for row in Product.objects.filter(id__in=list(product_ids), entity_id=entity_id).values("id", "preco_base", "ativo")
    }
    if not products:
        return {}

    date = date or timezone.localdate()
    listed = {}
    if price_list_id:
        price_list = (
            PriceList.objects.filter(id=price_list_id, entity_id=entity_id, active=True)
            .filter(Q(valid_from__isnull=True) | Q(valid_from__lte=date))
            .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=date))
            .first()
        )
        if price_list is not None:
            # the item for the highest min_quantity <= 1, per product
            for item in (
                PriceListItem.objects.filter(price_list=price_list, product_id__in=products, min_quantity__lte=Decimal("1"))
                .order_by("product_id", "-min_quantity")
            ):
                listed.setdefault(item.product_id, (item.price, str(price_list.id)))

    result = {}
    for product_id, row in products.items():
        price, price_list = listed.get(product_id, (row["preco_base"], None))
        result[product_id] = {"price": price, "price_list": price_list, "ativo": row["ativo"]}
    return result


def get_price_list_snapshot(price_list_id, entity_id):
    """{"id", "name"} of one of the Entity's price lists, or None."""
    try:
        price_list = PriceList.objects.filter(id=price_list_id, entity_id=entity_id).first()
    except (ValueError, ValidationError):
        return None
    return {"id": price_list.id, "name": price_list.name} if price_list else None


def get_product_snapshot(product_id, entity_id=None):
    """
    Leitura pública para outros módulos tirarem um snapshot pontual
    de um produto (ex.: sales guarda nome/código no momento da venda)
    sem importar inventory.models.Product diretamente.

    entity_id, when given, limits the lookup to that Entity's products
    (None = any Entity, the historical behaviour kept for sales).
    """

    products = Product.objects.all()
    if entity_id is not None:
        products = products.filter(entity_id=entity_id)

    try:
        product = products.get(id=product_id)
    except (Product.DoesNotExist, ValueError, ValidationError):
        return None

    return {
        "id": product.id,
        "codigo": product.codigo,
        "nome": product.nome,
        "preco_base": product.preco_base,
        "track_batches": product.track_batches,
        "product_type": product.product_type,
        "ativo": product.ativo,
    }
