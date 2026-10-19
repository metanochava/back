"""Marketplace of the pharmacies: the published pharmacies and their offers of
the common medicine catalogue, across Entities.

Cross-entity on purpose and READ ONLY. What leaves this module is the public
commercial face of a pharmacy - name, published contact, the Branch's main
address, the price it charges and whether it can sell - never cost, supplier,
movements, other products or anything clinical. Prices and stock are read live
from inventory's public services (farmacia never imports inventory models).

Eligible pharmacy = a published PharmacyListing whose Entity has the farmacia
module active (EntityApp). See docs/progress/farmacia-online.md.
"""
import math
from collections import defaultdict
from decimal import Decimal

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from django_resaas.saas.core.utils.full_path import FullPath
from django_resaas.saas.models.address import Address
from django_resaas.saas.models.entity_app import EntityApp

from inventory import services as inventory_services

from farmacia.models import MedicineCatalogItem, PharmacyListing, PharmacyOffer

# offers priced and sorted per search; a broader query must be refined
MAX_CANDIDATE_OFFERS = 300

SORT_PRICE = "price"
SORT_DISTANCE = "distance"
SORTS = (SORT_PRICE, SORT_DISTANCE)


class SearchTooBroad(Exception):
    pass


def _active_pharmacy_entities():
    return EntityApp.objects.filter(app__name="farmacia", state="Active").values("entity_id")


def eligible_listings():
    """Published listings of Entities with farmacia active; `sells` = the
    sales module is active too (an online order is collected as a Sale)."""
    return (
        PharmacyListing.objects.filter(published=True, entity_id__in=_active_pharmacy_entities())
        .annotate(sells=Exists(EntityApp.objects.filter(entity_id=OuterRef("entity_id"), app__name="sales",
                                                        state="Active")))
        .select_related("branch", "entity")
        .prefetch_related("branch__addresses")
    )


def _main_address(branch):
    # from the prefetched rows (branch.address would query again)
    return next((a for a in branch.addresses.all() if a.address_type == Address.AddressType.MAIN), None)


def distance_km(origin, coordinates):
    """Great-circle distance, or None without both points."""
    if not origin or not coordinates:
        return None
    lat1, lng1 = map(math.radians, (origin["lat"], origin["lng"]))
    lat2, lng2 = map(math.radians, (coordinates["lat"], coordinates["lng"]))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return round(6371.0088 * 2 * math.asin(math.sqrt(a)), 2)


def _pharmacy(listing, origin):
    address = _main_address(listing.branch)
    coordinates = address.coordinates if address else None
    return {
        "id": str(listing.id),
        "name": listing.branch.name,
        "organisation": listing.entity.name,
        "address": address.full_address if address else None,
        "city": (address.locality or None) if address else None,
        "neighborhood": (address.neighborhood or address.sublocality or None) if address else None,
        "country": (address.country or None) if address else None,
        "coordinates": coordinates,
        "distance_km": distance_km(origin, coordinates),
        "phone": listing.public_phone or None,
        "opening_hours": listing.opening_hours or None,
        "currency": listing.currency,
        "online_orders": listing.online_orders and listing.sells,
    }


def listings_of(branch_ids):
    """The listings of these Branches, published or not (an order keeps
    showing where it was placed)."""
    return (PharmacyListing.objects.filter(branch_id__in=list(branch_ids))
            .select_related("branch", "entity").prefetch_related("branch__addresses"))


def pharmacy_card(listing, order=None):
    """Public card of a pharmacy for an order (no distance)."""
    if listing is None:
        return {"id": None, "name": order.branch.name if order else None}
    listing.sells = getattr(listing, "sells", False)
    return _pharmacy(listing, None)


def _matches_place(pharmacy, *, q=None, country=None, city=None, neighborhood=None):
    def has(value, wanted):
        return not wanted or (value and wanted.lower() in value.lower())

    text = " ".join(filter(None, [pharmacy["name"], pharmacy["organisation"], pharmacy["address"]]))
    return (
        has(text, q)
        and has(pharmacy["country"], country)
        and has(pharmacy["city"], city)
        and has(pharmacy["neighborhood"], neighborhood)
    )


def _by_distance_then_name(item):
    # pharmacies without coordinates go last, never with an invented distance
    return (item["distance_km"] is None, item["distance_km"] or 0, item["name"].lower())


def pharmacies(*, origin=None, q=None, country=None, city=None, neighborhood=None, listing_id=None):
    """The eligible pharmacies, by distance from `origin` ({"lat","lng"}) when
    given (those without coordinates last), else by name."""
    listings = eligible_listings()
    if listing_id:
        listings = listings.filter(id=listing_id)
    result = [
        item for item in (_pharmacy(listing, origin) for listing in listings)
        if _matches_place(item, q=q, country=country, city=city, neighborhood=neighborhood)
    ]
    result.sort(key=_by_distance_then_name if origin else (lambda item: item["name"].lower()))
    return result


def _catalog_filter(q):
    """Every word of `q` must appear in some field of the catalogue item."""
    condition = Q()
    for word in (q or "").split():
        condition &= (
            Q(name__icontains=word) | Q(active_substance__icontains=word) | Q(brand__icontains=word)
            | Q(strength__icontains=word) | Q(dosage_form__icontains=word) | Q(presentation__icontains=word)
            | Q(code__iexact=word)
        )
    return condition


def _medicine(item):
    return {
        "id": str(item.id),
        "name": item.name,
        "active_substance": item.active_substance,
        "brand": item.brand or None,
        "strength": item.strength,
        "dosage_form": item.dosage_form,
        "presentation": item.presentation,
        "code": item.code,
        "prescription_required": item.prescription_required,
        # MEDIA paths; the view turns them into file URLs (photo_urls)
        "image": item.image.url if item.image else None,
        "media": [
            {"url": media.file.url, "kind": media.kind, "caption": media.caption or None}
            for media in item.media.all() if media.file
        ],
    }


def photo_urls(request, rows):
    """Turn the medicines' photo/video paths of these rows into signed file
    URLs (permanent tokens, like the catalogue serializers: public product
    media, never tenant data)."""
    for row in rows:
        medicine = row.get("medicine") or {}
        if medicine.get("image"):
            medicine["image"] = FullPath.url(request, medicine["image"], temporary=False)
        for media in medicine.get("media") or []:
            media["url"] = FullPath.url(request, media["url"], temporary=False)
    return rows


def search_offers(*, q=None, catalog_item_id=None, dosage_form=None, strength=None, listing_id=None,
                  origin=None, min_price=None, max_price=None, available_only=False, sort=SORT_PRICE):
    """
    Offers of the eligible pharmacies for the catalogue items matching the
    query: one row per (medicine, pharmacy) with that pharmacy's live price
    and availability. Never more than MAX_CANDIDATE_OFFERS are evaluated
    (SearchTooBroad otherwise: the caller asks for a narrower query).

    An offer whose product is inactive, missing or has no price is left out:
    without a price there is nothing to compare. A pharmacy without
    show_quantity tells only whether it can sell.
    """
    listings = {listing.branch_id: listing for listing in eligible_listings()}
    if listing_id:
        listings = {branch_id: listing for branch_id, listing in listings.items() if str(listing.id) == str(listing_id)}

    items = MedicineCatalogItem.objects.filter(active=True).filter(_catalog_filter(q))
    if catalog_item_id:
        items = items.filter(id=catalog_item_id)
    if dosage_form:
        items = items.filter(dosage_form__iexact=dosage_form)
    if strength:
        items = items.filter(strength__iexact=strength)

    offers = list(
        PharmacyOffer.objects.filter(active=True, branch_id__in=list(listings), catalog_item__in=items)
        .select_related("catalog_item").prefetch_related("catalog_item__media")[: MAX_CANDIDATE_OFFERS + 1]
    )
    if len(offers) > MAX_CANDIDATE_OFFERS:
        raise SearchTooBroad()

    # live price and stock, a fixed number of queries per pharmacy
    prices, stock = {}, {}
    groups = defaultdict(list)
    for offer in offers:
        groups[(offer.entity_id, offer.branch_id, offer.price_list_id)].append(offer.product_id)
    for (entity_id, branch_id, price_list_id), product_ids in groups.items():
        for product_id, price in inventory_services.get_prices(product_ids, entity_id, price_list_id).items():
            prices[(branch_id, price_list_id, product_id)] = price
    by_branch = defaultdict(set)
    for offer in offers:
        by_branch[(offer.entity_id, offer.branch_id)].add(offer.product_id)
    for (entity_id, branch_id), product_ids in by_branch.items():
        for product_id, quantity in inventory_services.branch_available_quantities(
            product_ids, entity_id=entity_id, branch_id=branch_id,
        ).items():
            stock[(branch_id, product_id)] = quantity

    checked_at = timezone.now().isoformat()
    pharmacies_cache = {}
    rows = []
    for offer in offers:
        price = prices.get((offer.branch_id, offer.price_list_id, offer.product_id))
        if not price or not price["ativo"] or price["price"] is None:
            continue
        listing = listings[offer.branch_id]
        quantity = stock.get((offer.branch_id, offer.product_id), Decimal("0"))
        # a service has no stock (None): it can always be sold
        available = quantity is None or quantity > 0
        if available_only and not available:
            continue
        if min_price is not None and price["price"] < min_price:
            continue
        if max_price is not None and price["price"] > max_price:
            continue
        if listing.id not in pharmacies_cache:
            pharmacies_cache[listing.id] = _pharmacy(listing, origin)
        rows.append({
            "offer_id": str(offer.id),
            "medicine": _medicine(offer.catalog_item),
            "pharmacy": pharmacies_cache[listing.id],
            "price": str(price["price"]),
            "currency": listing.currency,
            "price_source": "price_list" if price["price_list"] else "product",
            "available": available,
            "available_quantity": (
                str(max(quantity, Decimal("0")).normalize()) if listing.show_quantity and quantity is not None else None
            ),
            "online_sale": listing.online_orders and listing.sells and offer.online_sale,
            "checked_at": checked_at,
        })

    if sort == SORT_DISTANCE and origin:
        rows.sort(key=lambda row: (
            row["pharmacy"]["distance_km"] is None, row["pharmacy"]["distance_km"] or 0, Decimal(row["price"]),
        ))
    else:
        rows.sort(key=lambda row: (Decimal(row["price"]), row["pharmacy"]["name"].lower()))
    # what can be sold first, whatever the order
    rows.sort(key=lambda row: not row["available"])
    return rows
