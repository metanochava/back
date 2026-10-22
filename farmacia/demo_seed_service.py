"""Demo data for the online pharmacy (marketplace): a few FICTITIOUS pharmacies,
each its own Entity, with a published listing, products linked to the common
medicine catalogue, prices and stock, so the nearby-pharmacies list and the
medicine search can be tried on a fresh database. Used by
`manage.py seed_pharmacy_demo`.

Safety (CLAUDE.md §11, §76):
- every pharmacy is a NEW Entity whose name starts with DEMO_PREFIX; no real
  Entity, Branch, product, price or stock is ever read for writing or changed;
- catalogue items are matched on their unique key and reused as they are,
  never modified; missing ones are created with a DEMO- code;
- idempotent: an existing demo pharmacy, product or listing is reused and its
  stock is NOT topped up again (stock only enters, as an auditable movement,
  when the product is created);
- the actor is an existing user named by the operator (created_by / movement
  user). No user or password is ever created.
"""
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from django_resaas.saas.models.app import App
from django_resaas.saas.models.branch import Branch
from django_resaas.saas.models.entity import Entity
from django_resaas.saas.models.entity_app import EntityApp
from django_resaas.saas.models.entity_type import EntityType
from django_resaas.saas.models.user import User
from inventory import services as inventory_services
from inventory.models import Product, StockMovement, Warehouse

from farmacia.models import MedicineCatalogItem, PharmacyListing, PharmacyOffer

DEMO_PREFIX = "[DEMO] "
CODE_PREFIX = "DEMO-"
MODULES = ("farmacia", "inventory", "sales")

# name, city, neighbourhood, latitude, longitude (fictitious pharmacies, real towns)
PHARMACIES = [
    ("Farmácia Demo Baixa", "Maputo", "Baixa", "-25.9692", "32.5732"),
    ("Farmácia Demo Polana", "Maputo", "Polana", "-25.9623", "32.5958"),
    ("Farmácia Demo Machava", "Matola", "Machava", "-25.9175", "32.4870"),
    ("Farmácia Demo Sommerschield", "Maputo", "Sommerschield", "-25.9556", "32.6011"),
    ("Farmácia Demo Liberdade", "Matola", "Liberdade", "-25.9620", "32.4590"),
]

# --region: where the demo pharmacies are. "mozambique" is the default and uses
# PHARMACIES; the others let a developer try the map from where they are.
REGIONS = {
    "mozambique": dict(country="Mozambique", currency="MZN", phone="+258 00 000 0000", pharmacies=PHARMACIES),
    "ahmedabad": dict(country="India", currency="INR", phone="+91 00000 00000", pharmacies=[
        ("Farmácia Demo Chandkheda", "Ahmedabad", "Chandkheda", "23.1105", "72.5835"),
        ("Farmácia Demo Chandkheda Sul", "Ahmedabad", "Chandkheda", "23.1012", "72.5927"),
    ]),
}

# catalogue key, base price in MZN, prescription required
MEDICINES = [
    (("Paracetamol", "Paracetamol", "", "500 mg", "Tablet", "Box of 20 tablets"), "45", False),
    (("Ibuprofen", "Ibuprofen", "", "400 mg", "Tablet", "Box of 20 tablets"), "80", False),
    (("Amoxicillin", "Amoxicillin", "", "500 mg", "Capsule", "Box of 16 capsules"), "150", True),
    (("Amoxicillin", "Amoxicillin", "", "250 mg/5 ml", "Oral suspension", "Bottle of 100 ml"), "180", True),
    (("Metformin", "Metformin", "", "850 mg", "Tablet", "Box of 30 tablets"), "120", True),
    (("Oral rehydration salts", "Oral rehydration salts", "", "20.5 g", "Powder", "Sachet"), "15", False),
    (("Artemether + Lumefantrine", "Artemether + Lumefantrine", "", "20 mg/120 mg", "Tablet",
      "Box of 24 tablets"), "250", True),
    (("Cetirizine", "Cetirizine", "", "10 mg", "Tablet", "Box of 10 tablets"), "60", False),
]

CATALOG_FIELDS = ("name", "active_substance", "brand", "strength", "dosage_form", "presentation")


class SeedError(Exception):
    """A missing/ambiguous input - reported to the operator, nothing written."""


@dataclass
class SeedReport:
    actor: str = ""
    catalog_created: int = 0
    catalog_reused: int = 0
    pharmacies: list = field(default_factory=list)   # [{name, created, products, offers, stock}]

    def total(self, key):
        return sum(p[key] for p in self.pharmacies)


def resolve_actor(username):
    if not username:
        raise SeedError("--actor-user is required (username or email of an existing user).")
    user = User.objects.filter(Q(username__iexact=username) | Q(email__iexact=username)).first()
    if user is None:
        raise SeedError(f"User '{username}' not found.")
    return user


def resolve_entity_type(name):
    entity_type = EntityType.objects.filter(name__iexact=name).first()
    if entity_type is None:
        raise SeedError(f"EntityType '{name}' not found.")
    return entity_type


def resolve_apps():
    apps = {app.name: app for app in App.objects.filter(name__in=MODULES)}
    missing = [name for name in MODULES if name not in apps]
    if missing:
        raise SeedError(f"App(s) not registered: {', '.join(missing)}. Run resaas_setup first.")
    return apps


def ensure_catalog(report, *, dry_run):
    """{index: MedicineCatalogItem} for MEDICINES; existing items are reused untouched."""
    items = {}
    for index, (key, _, prescription) in enumerate(MEDICINES):
        values = dict(zip(CATALOG_FIELDS, key))
        lookup = {name: values[name] for name in CATALOG_FIELDS if name != "name"}
        item = MedicineCatalogItem.objects.filter(**lookup).first()
        if item:
            report.catalog_reused += 1
        else:
            report.catalog_created += 1
            item = MedicineCatalogItem(code=f"{CODE_PREFIX}MED-{index + 1:03d}", prescription_required=prescription,
                                       **values)
            if not dry_run:
                item.save()
        items[index] = item
    return items


def _price(base, pharmacy_index, medicine_index):
    """Deterministic spread of ±15% around the base price, so prices differ."""
    factor = Decimal(85 + (pharmacy_index * 7 + medicine_index * 5) % 31) / 100
    return (Decimal(base) * factor).quantize(Decimal("1"))


def _stock(pharmacy_index, medicine_index):
    """Deterministic quantity; some offers are sold out on purpose."""
    quantity = (pharmacy_index * 11 + medicine_index * 7) % 40
    return 0 if quantity < 6 else quantity


def ensure_pharmacy(index, spec, entity_type, apps, catalog, actor, *, dry_run, region=REGIONS["mozambique"]):
    name, city, neighbourhood, lat, lng = spec
    full_name = DEMO_PREFIX + name
    result = {"name": full_name, "created": False, "products": 0, "offers": 0, "stock": 0}

    entity = Entity.objects.filter(name=full_name, entity_type=entity_type).first()
    if entity is None:
        result["created"] = True
        if dry_run:
            result.update(products=len(MEDICINES), offers=len(MEDICINES),
                          stock=sum(_stock(index, m) for m in range(len(MEDICINES))))
            return result
        entity = Entity.objects.create(name=full_name, entity_type=entity_type)

    branch = Branch.objects.filter(entity=entity).order_by("created_at").first()
    if branch is None:
        result["created"] = True
        if dry_run:
            return result
        branch = Branch.objects.create(name=name, entity=entity)
        branch.set_address(locality=city, neighborhood=neighbourhood, country=region["country"],
                           formatted_address=f"{neighbourhood}, {city} (demo)", latitude=lat, longitude=lng)

    base = dict(entity=entity, branch=branch, created_by=actor, updated_by=actor)
    ctx = dict(entity_id=entity.id, branch_id=branch.id, user=actor)

    if not dry_run:
        for app in apps.values():
            EntityApp.objects.get_or_create(entity=entity, app=app, defaults={"state": "Active"})
        PharmacyListing.all_objects.get_or_create(
            branch=branch,
            defaults=dict(published=True, currency=region["currency"], public_phone=region["phone"],
                          opening_hours="Demo pharmacy - fictitious data", show_quantity=index % 2 == 0,
                          online_orders=True, entity=entity, created_by=actor, updated_by=actor),
        )
    warehouse = Warehouse.objects.filter(entity=entity, nome="Demo warehouse").first()
    if warehouse is None and not dry_run:
        warehouse = Warehouse.objects.create(nome="Demo warehouse", codigo=f"{CODE_PREFIX}WH", **base)

    today = timezone.localdate()
    for m, (_, base_price, _) in enumerate(MEDICINES):
        item = catalog[m]
        code = f"{CODE_PREFIX}{m + 1:03d}"
        product = Product.objects.filter(entity=entity, codigo=code).first()
        if product is None:
            result["products"] += 1
            quantity = _stock(index, m)
            result["stock"] += quantity
            if dry_run:
                result["offers"] += 1
                continue
            product = Product.objects.create(
                nome=f"{item.name} {item.strength} (demo)", codigo=code, preco_base=_price(base_price, index, m),
                track_batches=True, **base,
            )
            if quantity:
                batch = inventory_services.get_or_create_batch(
                    product=product, lot_number=f"{CODE_PREFIX}LOT-{m + 1:03d}",
                    expiry_date=today + timedelta(days=180 + 30 * m), **ctx,
                )
                inventory_services.apply_movement(product=product, warehouse=warehouse,
                                                  tipo=StockMovement.TIPO_ENTRADA, quantidade=Decimal(quantity),
                                                  batch=batch, **ctx)
        if dry_run:
            continue
        _, created = PharmacyOffer.all_objects.get_or_create(
            branch=branch, product_id=product.id,
            defaults=dict(catalog_item=item, entity=entity, created_by=actor, updated_by=actor),
        )
        result["offers"] += int(created)
    return result


def run(*, actor_user, entity_type="Farmacia", pharmacies=3, dry_run=False, region="mozambique"):
    if region not in REGIONS:
        raise SeedError(f"--region must be one of: {', '.join(REGIONS)}.")
    specs = REGIONS[region]["pharmacies"]
    if not 1 <= pharmacies <= len(specs):
        raise SeedError(f"--pharmacies must be between 1 and {len(specs)}.")
    report = SeedReport()
    actor = resolve_actor(actor_user)
    report.actor = actor.username
    kind = resolve_entity_type(entity_type)
    apps = resolve_apps()

    with transaction.atomic():
        catalog = ensure_catalog(report, dry_run=dry_run)
        for index, spec in enumerate(specs[:pharmacies]):
            report.pharmacies.append(ensure_pharmacy(index, spec, kind, apps, catalog, actor, dry_run=dry_run,
                                                     region=REGIONS[region]))
        if dry_run:
            transaction.set_rollback(True)
    return report
