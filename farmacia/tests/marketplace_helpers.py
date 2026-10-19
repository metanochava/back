"""Pharmacies with stock for the marketplace tests."""
import datetime
from decimal import Decimal

from django.utils import timezone

from inventory import services as inventory_services
from inventory.models import Product, StockMovement, Warehouse
from testutils.tenant import bootstrap_tenant

from farmacia.models import MedicineCatalogItem, PharmacyListing, PharmacyOffer


def medicine(name="Paracetamol", substance="Paracetamol", strength="500 mg", form="Tablet",
             presentation="Box of 20 tablets", **extra):
    return MedicineCatalogItem.objects.create(
        name=name, active_substance=substance, strength=strength, dosage_form=form,
        presentation=presentation, **extra,
    )


class Pharmacy:
    """A tenant (Entity + Branch, farmacia and inventory active) with a
    warehouse, a main address and, when `published`, a marketplace listing."""

    def __init__(self, label, *, lat=None, lng=None, city="Maputo", published=True, show_quantity=False,
                 online_orders=True, modules=("farmacia", "inventory")):
        self.tenant = bootstrap_tenant(label, modules=modules)
        self.entity, self.branch, self.user = self.tenant["entity"], self.tenant["branch"], self.tenant["user"]
        self.client = self.tenant["client"]
        address = {"locality": city, "country": "Mozambique", "formatted_address": f"Av. {label}, {city}"}
        if lat is not None:
            address.update(latitude=lat, longitude=lng)
        self.branch.set_address(**address)
        self.warehouse = Warehouse.objects.create(nome=f"Main {label}", **self.fields())
        self.listing = PharmacyListing.objects.create(
            published=published, currency="MZN", public_phone="+258 84 000 0000", opening_hours="Mon-Fri 8:00-20:00",
            show_quantity=show_quantity, online_orders=online_orders, **self.fields(),
        )

    def fields(self):
        return dict(entity=self.entity, branch=self.branch, created_by=self.user, updated_by=self.user)

    def offers(self):
        return PharmacyOffer.objects.filter(branch=self.branch)

    def ctx(self):
        return dict(entity_id=self.entity.id, branch_id=self.branch.id, user=self.user)

    def offer(self, item, *, price, stock=0, lots=None, online_sale=True, ativo=True):
        """A product of this pharmacy linked to `item`, priced `price`, with
        `stock` units (or `lots`: [(quantity, expiry_date)])."""
        product = Product.objects.create(
            nome=f"{item.name} {item.strength}", codigo=f"P-{Product.objects.count() + 1}",
            preco_base=Decimal(price), track_batches=bool(lots), ativo=ativo, **self.fields(),
        )
        if lots:
            for n, (quantity, expiry) in enumerate(lots, start=1):
                batch = inventory_services.get_or_create_batch(
                    product=product, lot_number=f"L{n}", expiry_date=expiry, **self.ctx(),
                )
                inventory_services.apply_movement(product=product, warehouse=self.warehouse,
                                                  tipo=StockMovement.TIPO_ENTRADA, quantidade=Decimal(quantity),
                                                  batch=batch, **self.ctx())
        elif stock:
            inventory_services.apply_movement(product=product, warehouse=self.warehouse,
                                              tipo=StockMovement.TIPO_ENTRADA, quantidade=Decimal(stock), **self.ctx())
        PharmacyOffer.objects.create(catalog_item=item, product_id=product.id, online_sale=online_sale, **self.fields())
        return product


def yesterday():
    return timezone.localdate() - datetime.timedelta(days=1)


def next_year():
    return timezone.localdate() + datetime.timedelta(days=365)
