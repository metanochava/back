"""A bar's catalogue (drinks, snacks and services) for an existing Entity, to
try the point of sale and its open tabs. Services (cover charge, table
reservation, corkage, ...) are catalogued services: they never move stock.

    python manage.py seed_bar_catalog_demo --entity Tsakane --actor-user Tsakane
    python manage.py seed_bar_catalog_demo --entity Tsakane --actor-user Tsakane --dry-run

Fictitious demo data: every item's code starts with "DEMO-BAR-" (names stay
clean for the point of sale), so they are recognisable and removable.
Idempotent: an item or category that already exists (same code / name in
the Entity) is kept as it is, never changed. Only the given Entity is
touched; no stock is received. On a database with DEBUG off it refuses to
run without --allow-production: demo items are not real data.
"""
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from catalog.models import Product, ProductCategory
from django_resaas.saas.models.branch import Branch
from django_resaas.saas.models.entity import Entity

CODE_PREFIX = "DEMO-BAR-"

# category -> [(code, name, unit, price in the Entity's currency)]
CATALOGUE = {
    "Cervejas": [
        ("2M", "2M (garrafa 340ml)", "un", "80"),
        ("LAUR-PRETA", "Laurentina Preta (garrafa 340ml)", "un", "90"),
        ("LAUR-CLARA", "Laurentina Clara (garrafa 340ml)", "un", "85"),
        ("MANICA", "Manica (garrafa 340ml)", "un", "80"),
        ("CASTLE-LITE", "Castle Lite (lata 330ml)", "un", "95"),
        ("HEINEKEN", "Heineken (garrafa 330ml)", "un", "120"),
        ("2M-PRESSAO", "2M de pressão (copo)", "un", "70"),
    ],
    "Refrigerantes e águas": [
        ("COCA-COLA", "Coca-Cola (lata 330ml)", "un", "60"),
        ("FANTA", "Fanta Laranja (lata 330ml)", "un", "60"),
        ("SPRITE", "Sprite (lata 330ml)", "un", "60"),
        ("TONICA", "Água tónica (lata 330ml)", "un", "65"),
        ("AGUA-500", "Água mineral 500ml", "un", "40"),
        ("AGUA-GAS", "Água com gás 500ml", "un", "50"),
        ("SUMO", "Sumo de fruta (copo)", "un", "90"),
        ("RED-BULL", "Red Bull (lata 250ml)", "un", "150"),
    ],
    "Bebidas espirituosas": [
        ("WHISKY-DOSE", "Whisky (dose)", "dose", "130"),
        ("VODKA-DOSE", "Vodka (dose)", "dose", "100"),
        ("GIN-DOSE", "Gin (dose)", "dose", "120"),
        ("RUM-DOSE", "Rum (dose)", "dose", "100"),
        ("TEQUILA-DOSE", "Tequila (dose)", "dose", "120"),
        ("TIPO-TINTO", "Tipo Tinto (dose)", "dose", "70"),
        ("AMARULA", "Amarula (dose)", "dose", "110"),
    ],
    "Vinhos": [
        ("VINHO-TINTO-COPO", "Vinho tinto (copo)", "un", "150"),
        ("VINHO-BRANCO-COPO", "Vinho branco (copo)", "un", "150"),
        ("VINHO-TINTO-GARRAFA", "Vinho tinto (garrafa)", "un", "950"),
        ("ESPUMANTE", "Espumante (garrafa)", "un", "1200"),
    ],
    "Cocktails": [
        ("CAIPIRINHA", "Caipirinha", "un", "250"),
        ("MOJITO", "Mojito", "un", "280"),
        ("GIN-TONICO", "Gin tónico", "un", "260"),
        ("PINA-COLADA", "Piña colada", "un", "300"),
        ("SEX-ON-THE-BEACH", "Sex on the beach", "un", "300"),
    ],
    "Petiscos": [
        ("BATATA-FRITA", "Batata frita", "un", "150"),
        ("AMENDOIM", "Amendoim torrado", "un", "80"),
        ("RISSOIS", "Rissóis de camarão (3 un)", "un", "180"),
        ("ASAS-FRANGO", "Asas de frango picantes", "un", "350"),
        ("PREGO", "Prego no pão", "un", "250"),
        ("CHAMUCAS", "Chamuças (3 un)", "un", "150"),
        ("TABUA-MISTA", "Tábua mista", "un", "650"),
    ],
    "Serviços": [
        ("ENTRADA", "Entrada (noite com DJ)", "un", "200"),
        ("COUVERT", "Couvert artístico (música ao vivo)", "un", "150"),
        ("RESERVA-MESA", "Reserva de mesa", "un", "300"),
        ("MESA-VIP", "Mesa VIP (noite)", "un", "2500"),
        ("ROLHA", "Taxa de rolha (garrafa trazida)", "un", "500"),
        ("KARAOKE", "Karaoke (hora)", "hora", "800"),
        ("ESPACO-EVENTO", "Aluguer do espaço para eventos (hora)", "hora", "3000"),
        ("DECORACAO", "Decoração de aniversário", "un", "1500"),
        ("ENTREGA", "Entrega ao domicílio", "un", "150"),
    ],
}

# the categories whose items are services (no stock)
SERVICE_CATEGORIES = {"Serviços"}


class Command(BaseCommand):
    help = "Creates a fictitious bar catalogue (drinks, snacks and services, codes DEMO-BAR-*) for an existing Entity."

    def add_arguments(self, parser):
        parser.add_argument("--entity", required=True, help="Name or id of the Entity that sells them.")
        parser.add_argument("--actor-user", required=True,
                            help="Username or email of an existing user, recorded as author of the demo data.")
        parser.add_argument("--branch", help="Branch name (default: the Entity's only / first branch by name).")
        parser.add_argument("--dry-run", action="store_true", help="Show what would be created, write nothing.")
        parser.add_argument("--allow-production", action="store_true", help="Required when DEBUG is off.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["allow_production"]:
            raise CommandError("DEBUG is off: this looks like production. Demo items are not real data; "
                               "pass --allow-production if you really want them here.")

        entity = self._entity(options["entity"])
        actor = self._actor(options["actor_user"])
        branch = self._branch(entity, options.get("branch"))
        audit = {"entity": entity, "branch": branch, "created_by": actor, "updated_by": actor, "state": "Active"}

        created = {"categories": 0, "products": 0}
        kept = {"categories": 0, "products": 0}
        with transaction.atomic():
            for category_name, items in CATALOGUE.items():
                category = ProductCategory.objects.filter(entity=entity, nome=category_name).first()
                if category is None:
                    created["categories"] += 1
                    if not options["dry_run"]:
                        category = ProductCategory.objects.create(nome=category_name, ativo=True, **audit)
                else:
                    kept["categories"] += 1
                for code, name, unit, price in items:
                    codigo = CODE_PREFIX + code
                    if Product.all_objects.filter(entity=entity, codigo=codigo).exists():
                        kept["products"] += 1
                        continue
                    created["products"] += 1
                    if not options["dry_run"]:
                        Product.objects.create(
                            codigo=codigo, nome=name, categoria=category, unidade=unit,
                            preco_base=Decimal(price), ativo=True,
                            product_type=(Product.TYPE_SERVICE if category_name in SERVICE_CATEGORIES
                                          else Product.TYPE_GOODS),
                            **audit,
                        )
            if options["dry_run"]:
                transaction.set_rollback(True)

        verb = "to create" if options["dry_run"] else "created"
        self.stdout.write(self.style.MIGRATE_HEADING(
            "DRY RUN - nothing written" if options["dry_run"] else "Bar catalogue demo data (fictitious)"))
        self.stdout.write(f"Entity: {entity.name} | branch: {branch.name if branch else '-'} | actor: {actor}")
        self.stdout.write(self.style.SUCCESS(
            f"Categories {verb}: {created['categories']} (existing kept: {kept['categories']}) | "
            f"products {verb}: {created['products']} (existing kept: {kept['products']})"))

    def _entity(self, value):
        query = Q(name=value)
        try:
            import uuid
            query |= Q(id=uuid.UUID(str(value)))
        except ValueError:
            pass
        matches = list(Entity.objects.filter(query)[:2])
        if len(matches) != 1:
            raise CommandError(f"Entity '{value}' not found or not unique.")
        return matches[0]

    def _actor(self, value):
        user = get_user_model().objects.filter(Q(username=value) | Q(email=value)).first()
        if user is None:
            raise CommandError(f"User '{value}' not found.")
        return user

    def _branch(self, entity, name):
        branches = Branch.objects.filter(entity=entity).order_by("name")
        if name:
            branch = branches.filter(name=name).first()
            if branch is None:
                raise CommandError(f"Branch '{name}' not found in {entity.name}.")
            return branch
        return branches.first()
