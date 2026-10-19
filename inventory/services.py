"""
Camada de serviço do inventory. Única forma permitida de alterar stock.

Interface pública usada por outros módulos (ex.: sales, farmacia):
    - inventory_module_active(entity_id)
    - reserve_stock(lines, warehouse_id, entity_id)
    - apply_movement(...)
    - transfer_stock(...)
    - commit_sale_movements(sale, user)
    - revert_sale_movements(sale, user)
    - commit_dispensation_movements(dispensation, user)
    - commit_purchase_receipt_movements(...)  (purchases)
    - get_warehouse_snapshot(warehouse_id, entity_id)
    - reserve_document / release_reservations / consume_reservations
    - revert_dispensation_movements(dispensation, user)
    - finalize_inventory_count(inventory_count, user)

Outros módulos (sales, farmacia, ...) só devem importar deste
ficheiro — nunca importar models do inventory diretamente para
escrever dados.
"""

import datetime
import uuid
from decimal import Decimal

from django.db import transaction, IntegrityError
from django.db.models import F, Q, Sum
from django.core.exceptions import ValidationError
from django.utils import timezone

from django_resaas.saas.models.app import App
from django_resaas.saas.models.entity_app import EntityApp

from inventory.models import (
    PriceList,
    PriceListItem,
    StockReservation,
    Batch,
    BatchStock,
    Product,
    Warehouse,
    StockItem,
    StockMovement,
    InventorySetting,
    InventoryCount,
)


# =========================================================
# 🔌 ATIVAÇÃO DO MÓDULO
# =========================================================

def inventory_module_active(entity_id):
    """
    True se o módulo 'inventory' estiver ativo (EntityApp) para a entity.

    Usado por 'sales' para decidir se deve tentar movimentar stock ao
    confirmar uma venda, ou degradar (venda sem controlo de stock).
    """

    if not entity_id:
        return False

    return EntityApp.objects.filter(
        entity_id=entity_id,
        app__name="inventory",
        state="Active"
    ).exists()


# =========================================================
# ⚙️ CONFIGURAÇÃO POR ENTITY
# =========================================================

def _allow_negative_stock(entity_id):
    settings = InventorySetting.objects.filter(entity_id=entity_id).first()
    return bool(settings and settings.allow_negative_stock)


# =========================================================
# 🔒 LOCK / GET-OR-CREATE SEGURO DA LINHA DE STOCK
# =========================================================

def _lock_stock_item(*, product, warehouse, entity_id, branch_id, user):
    """
    Devolve o StockItem bloqueado (select_for_update) para a combinação
    (product, warehouse), criando-o com saldo 0 se ainda não existir.

    Só deve ser chamado dentro de uma transaction.atomic() já aberta.
    """

    try:
        return (
            StockItem.objects
            .select_for_update()
            .get(product=product, warehouse=warehouse)
        )

    except StockItem.DoesNotExist:
        try:
            with transaction.atomic():
                StockItem.objects.create(
                    product=product,
                    warehouse=warehouse,
                    quantidade=Decimal("0"),
                    entity_id=entity_id,
                    branch_id=branch_id,
                    created_by=user,
                    updated_by=user,
                )
        except IntegrityError:
            # corrida: outra transação criou a linha entretanto
            pass

        return (
            StockItem.objects
            .select_for_update()
            .get(product=product, warehouse=warehouse)
        )


def _lock_batch_stock(*, batch, warehouse, entity_id, branch_id, user):
    """Same as _lock_stock_item, for the balance of one lot in a warehouse."""

    try:
        return BatchStock.objects.select_for_update().get(batch=batch, warehouse=warehouse)
    except BatchStock.DoesNotExist:
        try:
            with transaction.atomic():
                BatchStock.objects.create(
                    batch=batch, warehouse=warehouse, quantity=Decimal("0"), state="Active",
                    entity_id=entity_id, branch_id=branch_id, created_by=user, updated_by=user,
                )
        except IntegrityError:
            pass
        return BatchStock.objects.select_for_update().get(batch=batch, warehouse=warehouse)


# =========================================================
# 🏷️ LOTS (BATCH TRACKING)
# =========================================================

def get_or_create_batch(*, product, lot_number, expiry_date=None, entity_id, branch_id, user):
    """The product's lot with this number in the Entity, created when new. An
    existing lot keeps its expiry date: a different one is refused."""

    lot_number = (lot_number or "").strip()
    if not lot_number:
        raise ValidationError("A lot number is required for this product.")

    batch = Batch.objects.filter(entity_id=entity_id, product=product, lot_number=lot_number).first()
    if batch is None:
        try:
            with transaction.atomic():
                return Batch.objects.create(
                    product=product, lot_number=lot_number, expiry_date=expiry_date, state="Active",
                    entity_id=entity_id, branch_id=branch_id, created_by=user, updated_by=user,
                )
        except IntegrityError:
            batch = Batch.objects.get(entity_id=entity_id, product=product, lot_number=lot_number)

    if expiry_date and batch.expiry_date and batch.expiry_date != expiry_date:
        raise ValidationError("This lot already exists with another expiry date.")
    if expiry_date and not batch.expiry_date:
        batch.expiry_date = expiry_date
        batch.save(update_fields=["expiry_date", "updated_at"])
    return batch


def _allocation_strategy(entity_id):
    settings = InventorySetting.objects.filter(entity_id=entity_id).first()
    return settings.allocation_strategy if settings else InventorySetting.ALLOCATION_FEFO


def allocate_batches(*, product, warehouse, quantity, entity_id):
    """[(batch, quantity)] that cover `quantity` from the warehouse's lots,
    by the Entity's strategy - FEFO (earliest expiry first, lots without
    expiry last) or FIFO (oldest lot first). Expired lots are never
    allocated. Rows are locked. Not enough stock -> ValidationError."""

    today = timezone.localdate()
    stocks = (
        BatchStock.objects.select_for_update(of=("self",))
        .select_related("batch")
        .filter(warehouse=warehouse, batch__product=product, quantity__gt=0)
        .exclude(batch__expiry_date__lt=today)
    )
    if _allocation_strategy(entity_id) == InventorySetting.ALLOCATION_FIFO:
        stocks = stocks.order_by("batch__created_at")
    else:
        stocks = stocks.order_by(F("batch__expiry_date").asc(nulls_last=True), "batch__created_at")

    remaining = Decimal(quantity)
    allocation = []
    for stock in stocks:
        if remaining <= 0:
            break
        take = min(stock.quantity, remaining)
        allocation.append((stock.batch, take))
        remaining -= take

    if remaining > 0:
        raise ValidationError("Not enough stock in valid (not expired) lots.")
    return allocation


def issue_stock(*, product, warehouse, quantidade, tipo, entity_id, branch_id, user, batch=None, **extra):
    """Outbound movement(s) of `quantidade` (> 0). For a product with batch
    tracking and no lot named, the lots are allocated (allocate_batches) and
    one movement is made per lot. Returns the list of movements."""

    quantidade = Decimal(quantidade)
    if not product.track_batches or batch is not None:
        movement, _ = apply_movement(
            product=product, warehouse=warehouse, tipo=tipo, quantidade=-quantidade, batch=batch,
            entity_id=entity_id, branch_id=branch_id, user=user, **extra,
        )
        return [movement]

    return [
        apply_movement(
            product=product, warehouse=warehouse, tipo=tipo, quantidade=-taken, batch=lot,
            entity_id=entity_id, branch_id=branch_id, user=user, **extra,
        )[0]
        for lot, taken in allocate_batches(product=product, warehouse=warehouse, quantity=quantidade, entity_id=entity_id)
    ]


def reverse_document_movements(*, documento_origem_tipo, documento_origem_id, entity_id, branch_id, user, motivo):
    """Return movements (TIPO_DEVOLUCAO) that undo every outbound movement of
    a document, lot by lot. The original movements are never touched."""

    originals = StockMovement.objects.select_related("product", "warehouse", "batch").filter(
        entity_id=entity_id,
        documento_origem_tipo=documento_origem_tipo,
        documento_origem_id=documento_origem_id,
        tipo=StockMovement.TIPO_SAIDA,
    )
    return [
        apply_movement(
            product=original.product, warehouse=original.warehouse, tipo=StockMovement.TIPO_DEVOLUCAO,
            quantidade=-original.quantidade, batch=original.batch, motivo=motivo,
            documento_origem_tipo=documento_origem_tipo, documento_origem_id=documento_origem_id,
            entity_id=entity_id, branch_id=branch_id, user=user,
        )[0]
        for original in originals
    ]


def expiring_batches(entity_id, days=30, warehouse_id=None):
    """Lot balances > 0 whose lot expires within `days` (or already expired)."""

    limit = timezone.localdate() + datetime.timedelta(days=int(days))
    stocks = (
        BatchStock.objects.select_related("batch", "batch__product", "warehouse")
        .filter(entity_id=entity_id, quantity__gt=0, batch__expiry_date__isnull=False, batch__expiry_date__lte=limit)
        .order_by("batch__expiry_date")
    )
    if warehouse_id:
        stocks = stocks.filter(warehouse_id=warehouse_id)
    today = timezone.localdate()
    return [
        {
            "batch": str(stock.batch_id),
            "lot_number": stock.batch.lot_number,
            "expiry_date": stock.batch.expiry_date,
            "expired": stock.batch.expiry_date < today,
            "days_left": (stock.batch.expiry_date - today).days,
            "product": str(stock.batch.product_id),
            "product_name": stock.batch.product.nome,
            "warehouse": str(stock.warehouse_id),
            "warehouse_name": stock.warehouse.nome,
            "quantity": stock.quantity,
        }
        for stock in stocks
    ]


# =========================================================
# 🏷️ CATALOGUE: SERVICES, VARIANTS, PRICES
# =========================================================

def holds_stock(product):
    """Goods hold stock; a service never does, nor does a product that has
    variants (its variants hold it)."""
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


# =========================================================
# 🔐 RESERVATIONS
# =========================================================

def _holding(queryset):
    """Active reservations that still hold stock (not expired)."""
    return queryset.filter(status=StockReservation.STATUS_ACTIVE).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    )


def reserved_quantity(*, product_id, warehouse_id, exclude_source=None):
    """Quantity held by active reservations, optionally without those of one
    document (source_type, source_id) - its own reservation is its stock."""
    reservations = _holding(StockReservation.objects.filter(product_id=product_id, warehouse_id=warehouse_id))
    if exclude_source:
        reservations = reservations.exclude(source_type=exclude_source[0], source_id=str(exclude_source[1]))
    return reservations.aggregate(total=Sum("quantity"))["total"] or Decimal("0")


def _usable_on_hand(product, warehouse, stock_item):
    """On hand that can leave: for a product with lots, only valid lots."""
    if not product.track_batches:
        return stock_item.quantidade
    return (
        BatchStock.objects.filter(batch__product=product, warehouse=warehouse)
        .exclude(batch__expiry_date__lt=timezone.localdate())
        .aggregate(total=Sum("quantity"))["total"] or Decimal("0")
    )


@transaction.atomic
def reserve(*, product, warehouse, quantity, source_type, source_id, entity_id, branch_id, user,
            expires_at=None, reason=None):
    """Holds `quantity` of a product in a warehouse for a document. Calling it
    again for the same document, product and warehouse replaces the quantity
    (idempotent). Refused when not enough is available (on hand - what other
    documents hold)."""

    quantity = Decimal(quantity)
    if quantity <= 0:
        raise ValidationError("The quantity must be greater than zero.")
    if str(product.entity_id) != str(entity_id) or str(warehouse.entity_id) != str(entity_id):
        raise ValidationError("Product not found.")

    # the balance row serializes reservations and movements of this product/warehouse
    stock_item = _lock_stock_item(product=product, warehouse=warehouse, entity_id=entity_id, branch_id=branch_id, user=user)
    others = reserved_quantity(product_id=product.id, warehouse_id=warehouse.id, exclude_source=(source_type, source_id))
    if _usable_on_hand(product, warehouse, stock_item) - others < quantity:
        raise ValidationError("Not enough available stock to reserve.")

    existing = StockReservation.objects.filter(
        entity_id=entity_id, source_type=source_type, source_id=str(source_id),
        product=product, warehouse=warehouse, status=StockReservation.STATUS_ACTIVE,
    ).first()
    if existing is not None:
        existing.quantity, existing.expires_at, existing.reason = quantity, expires_at, reason
        existing.updated_by = user
        existing.save(update_fields=["quantity", "expires_at", "reason", "updated_by", "updated_at"])
        return existing

    return StockReservation.objects.create(
        product=product, warehouse=warehouse, quantity=quantity, source_type=source_type,
        source_id=str(source_id), expires_at=expires_at, reason=reason, state="Active",
        entity_id=entity_id, branch_id=branch_id, created_by=user, updated_by=user,
    )


@transaction.atomic
def reserve_document(*, source_type, source_id, warehouse_id, lines, entity_id, branch_id, user, expires_at=None):
    """Public entry for other modules: (re)reserves a document's stock -
    lines is {product_id: quantity}. The document's previous reservations are
    released first, so calling it again reflects its current lines. All or
    nothing."""

    warehouse = _entity_warehouse(warehouse_id, entity_id)
    release_reservations(source_type=source_type, source_id=source_id, entity_id=entity_id, user=user)
    products = [(_entity_product(product_id, entity_id), quantity) for product_id, quantity in lines.items()]
    return [
        reserve(
            product=product, warehouse=warehouse, quantity=quantity,
            source_type=source_type, source_id=source_id, expires_at=expires_at,
            entity_id=entity_id, branch_id=branch_id, user=user,
        )
        for product, quantity in products
        if product.product_type != Product.TYPE_SERVICE
    ]


def _close_reservations(source_type, source_id, entity_id, user, status):
    return StockReservation.objects.filter(
        entity_id=entity_id, source_type=source_type, source_id=str(source_id),
        status=StockReservation.STATUS_ACTIVE,
    ).update(status=status, updated_by=user, updated_at=timezone.now())


def release_reservations(*, source_type, source_id, entity_id, user):
    """The document gave the stock up (e.g. cancelled)."""
    return _close_reservations(source_type, source_id, entity_id, user, StockReservation.STATUS_RELEASED)


def consume_reservations(*, source_type, source_id, entity_id, user):
    """The document took its stock (its outbound movements were made)."""
    return _close_reservations(source_type, source_id, entity_id, user, StockReservation.STATUS_CONSUMED)


# =========================================================
# 📖 DISPONIBILIDADE (SEM CRIAR MOVIMENTO)
# =========================================================

def reserve_stock(lines, *, warehouse_id, entity_id, exclude_source=None):
    """
    Verifica disponibilidade de uma lista de linhas SEM criar nenhum
    movimento. Não é uma reserva "dura" (não bloqueia stock para
    outros) — serve para dar feedback (ex.: aviso no carrinho de
    vendas) antes da confirmação real, que é sempre feita por
    commit_sale_movements().

    lines: iterável de {"product_id": ..., "quantidade": Decimal}

    Devolve lista de dicts:
        {"product_id", "quantidade_pedida", "quantidade_disponivel", "disponivel": bool}
    """

    allow_negative = _allow_negative_stock(entity_id)

    saldo_por_produto = {
        row["product_id"]: row["quantidade"]
        for row in StockItem.objects.filter(
            warehouse_id=warehouse_id,
            product_id__in=[line["product_id"] for line in lines]
        ).values("product_id", "quantidade")
    }

    # products with lots: only lots that are not expired can be sold
    from django.db.models import Sum

    tracked = set(
        Product.objects.filter(id__in=[line["product_id"] for line in lines], track_batches=True)
        .values_list("id", flat=True)
    )
    if tracked:
        valid = {
            row["batch__product_id"]: row["total"]
            for row in BatchStock.objects.filter(warehouse_id=warehouse_id, batch__product_id__in=tracked)
            .exclude(batch__expiry_date__lt=timezone.localdate())
            .values("batch__product_id").annotate(total=Sum("quantity"))
        }
        for product_id in tracked:
            saldo_por_produto[product_id] = valid.get(product_id) or Decimal("0")

    services_ids = set(
        Product.objects.filter(id__in=[line["product_id"] for line in lines], product_type=Product.TYPE_SERVICE)
        .values_list("id", flat=True)
    )

    resultado = []

    for line in lines:
        if line["product_id"] in services_ids:
            # a service has no stock: always available
            resultado.append({
                "product_id": line["product_id"],
                "quantidade_pedida": Decimal(line["quantidade"]),
                "quantidade_disponivel": None,
                "disponivel": True,
            })
            continue

        # what other documents reserved is not available (exclude_source: the
        # caller's own reservation still counts as its stock)
        disponivel = saldo_por_produto.get(line["product_id"], Decimal("0")) - reserved_quantity(
            product_id=line["product_id"], warehouse_id=warehouse_id, exclude_source=exclude_source,
        )
        pedida = Decimal(line["quantidade"])

        resultado.append({
            "product_id": line["product_id"],
            "quantidade_pedida": pedida,
            "quantidade_disponivel": disponivel,
            "disponivel": (allow_negative and line["product_id"] not in tracked) or disponivel >= pedida,
        })

    return resultado


def branch_available_quantities(product_ids, *, entity_id, branch_id):
    """
    {product_id: quantity} that can still be sold of each of the Entity's
    products, summed over the Branch's active warehouses: on hand (for a
    product with lots, only lots that are not expired) minus what active
    reservations hold - the same rule as reserve_stock(). A service maps to
    None (it has no stock); an unknown product, or one of another Entity, is
    left out. Read only: nothing is reserved.
    """

    product_ids = list(product_ids)
    if not product_ids:
        return {}

    products = dict(Product.objects.filter(id__in=product_ids, entity_id=entity_id).values_list("id", "product_type"))
    services_ids = {product_id for product_id, kind in products.items() if kind == Product.TYPE_SERVICE}
    lines = [{"product_id": product_id, "quantidade": Decimal("0")} for product_id in products if product_id not in services_ids]
    totals = {product_id: (None if product_id in services_ids else Decimal("0")) for product_id in products}

    warehouses = Warehouse.objects.filter(entity_id=entity_id, branch_id=branch_id, ativo=True).values_list("id", flat=True)
    for warehouse_id in warehouses:
        for row in reserve_stock(lines, warehouse_id=warehouse_id, entity_id=entity_id):
            totals[row["product_id"]] += row["quantidade_disponivel"]

    return totals


def branch_warehouse_for(lines, *, entity_id, branch_id):
    """
    id of the first active warehouse of the Branch (by name) that can serve
    EVERY line on its own - lines is {product_id: quantity} - or None. Same
    availability rule as reserve_stock(). Read only: the caller reserves.
    """

    wanted = [{"product_id": product_id, "quantidade": Decimal(quantity)} for product_id, quantity in lines.items()]
    if not wanted:
        return None
    warehouses = Warehouse.objects.filter(entity_id=entity_id, branch_id=branch_id, ativo=True).order_by("nome")
    for warehouse_id in warehouses.values_list("id", flat=True):
        if all(row["disponivel"] for row in reserve_stock(wanted, warehouse_id=warehouse_id, entity_id=entity_id)):
            return warehouse_id
    return None


# =========================================================
# ✍️ MOVIMENTO (ÚNICO PONTO DE ESCRITA DE STOCK)
# =========================================================

@transaction.atomic
def apply_movement(
    *,
    product,
    warehouse,
    tipo,
    quantidade,
    entity_id,
    branch_id,
    user,
    motivo=None,
    custo_unitario=None,
    documento_origem_tipo=None,
    documento_origem_id=None,
    batch=None,
):
    """
    Cria um StockMovement e atualiza o StockItem correspondente na
    mesma transação, com lock de linha (select_for_update) para
    evitar corrida entre operações concorrentes sobre o mesmo
    (product, warehouse).

    Lots: a product with track_batches needs `batch` (one of its lots); the
    lot's balance in the warehouse (BatchStock) moves with StockItem and never
    goes below zero, and an expired lot cannot leave as a sale/outbound
    (TIPO_SAIDA). A product without batch tracking refuses a lot.
    """

    quantidade = Decimal(quantidade)

    if quantidade == 0:
        raise ValidationError("Quantidade do movimento não pode ser zero.")

    if tipo == StockMovement.TIPO_AJUSTE and not motivo:
        raise ValidationError("Motivo é obrigatório para movimentos de ajuste.")

    if not holds_stock(product):
        raise ValidationError(
            "A service has no stock." if product.product_type == Product.TYPE_SERVICE
            else "Stock is kept on the variants of this product."
        )

    batch_stock = None
    if product.track_batches:
        if batch is None:
            raise ValidationError("A lot is required for this product.")
        if batch.product_id != product.id:
            raise ValidationError("This lot belongs to another product.")
        if (
            quantidade < 0 and tipo == StockMovement.TIPO_SAIDA
            and batch.expiry_date and batch.expiry_date < timezone.localdate()
        ):
            raise ValidationError("This lot is expired.")
        batch_stock = _lock_batch_stock(
            batch=batch, warehouse=warehouse, entity_id=entity_id, branch_id=branch_id, user=user,
        )
        if batch_stock.quantity + quantidade < 0:
            raise ValidationError("Not enough stock in this lot.")
    elif batch is not None:
        raise ValidationError("This product does not track lots.")

    stock_item = _lock_stock_item(
        product=product,
        warehouse=warehouse,
        entity_id=entity_id,
        branch_id=branch_id,
        user=user,
    )

    novo_saldo = stock_item.quantidade + quantidade

    # an outbound movement may not take stock other documents reserved
    # (adjustments record reality and are not limited)
    if quantidade < 0 and tipo in (StockMovement.TIPO_SAIDA, StockMovement.TIPO_TRANSFERENCIA):
        own = (documento_origem_tipo, documento_origem_id) if documento_origem_id else None
        held = reserved_quantity(product_id=product.id, warehouse_id=warehouse.id, exclude_source=own)
        if held > 0 and novo_saldo < held:
            raise ValidationError("This stock is reserved for other documents.")

    if novo_saldo < 0 and (product.track_batches or not _allow_negative_stock(entity_id)):
        raise ValidationError(
            f"Stock insuficiente para '{product.nome}' em '{warehouse.nome}' "
            f"(saldo atual: {stock_item.quantidade}, necessário: {-quantidade})."
        )

    movement = StockMovement.objects.create(
        product=product,
        warehouse=warehouse,
        tipo=tipo,
        quantidade=quantidade,
        motivo=motivo,
        custo_unitario=custo_unitario,
        documento_origem_tipo=documento_origem_tipo,
        documento_origem_id=documento_origem_id,
        batch=batch,
        entity_id=entity_id,
        branch_id=branch_id,
        created_by=user,
        updated_by=user,
    )

    if batch_stock is not None:
        batch_stock.quantity += quantidade
        batch_stock.updated_by = user
        batch_stock.save(update_fields=["quantity", "updated_by", "updated_at"])

    stock_item.quantidade = novo_saldo
    stock_item.updated_by = user
    stock_item.save(update_fields=["quantidade", "updated_by", "updated_at"])

    return movement, stock_item


# =========================================================
# 🔁 TRANSFERÊNCIA ENTRE ARMAZÉNS (2 MOVIMENTOS ATÓMICOS)
# =========================================================

@transaction.atomic
def transfer_stock(
    *,
    product,
    warehouse_origem,
    warehouse_destino,
    quantidade,
    entity_id,
    branch_id,
    user,
    motivo=None,
    batch=None,
):
    quantidade = Decimal(quantidade)

    if quantidade <= 0:
        raise ValidationError("Quantidade de transferência deve ser positiva.")

    if warehouse_origem.id == warehouse_destino.id:
        raise ValidationError("Armazém de origem e destino não podem ser iguais.")

    ref_id = uuid.uuid4()
    common = dict(
        tipo=StockMovement.TIPO_TRANSFERENCIA, motivo=motivo, documento_origem_tipo="transferencia",
        documento_origem_id=ref_id, entity_id=entity_id, branch_id=branch_id, user=user,
    )

    # lot by lot for a product with batch tracking (the given lot, or FEFO/FIFO)
    saidas = issue_stock(product=product, warehouse=warehouse_origem, quantidade=quantidade, batch=batch, **common)
    entradas = [
        apply_movement(
            product=product, warehouse=warehouse_destino, quantidade=-saida.quantidade, batch=saida.batch, **common
        )[0]
        for saida in saidas
    ]

    # (first outbound, first inbound) - one of each for a product without lots
    return saidas[0], entradas[0]


# =========================================================
# 📖 LEITURA PÚBLICA (para outros módulos, ex.: sales)
# =========================================================

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


def get_warehouse_name(warehouse_id):
    if not warehouse_id:
        return None

    warehouse = Warehouse.objects.filter(id=warehouse_id).first()
    return warehouse.nome if warehouse else None


def get_warehouse_snapshot(warehouse_id, entity_id):
    """{"id", "nome"} of an Entity's warehouse, or None (unknown id or
    another Entity's warehouse)."""

    if not warehouse_id:
        return None

    try:
        warehouse = Warehouse.objects.filter(id=warehouse_id, entity_id=entity_id).first()
    except (ValueError, ValidationError):
        return None

    return {"id": warehouse.id, "nome": warehouse.nome} if warehouse else None


def _entity_warehouse(warehouse_id, entity_id):
    warehouse = Warehouse.objects.filter(id=warehouse_id, entity_id=entity_id).first()
    if warehouse is None:
        raise ValidationError("Warehouse not found.")
    return warehouse


def _entity_product(product_id, entity_id):
    product = Product.objects.filter(id=product_id, entity_id=entity_id).first()
    if product is None:
        raise ValidationError("Product not found.")
    return product


def _item_batch(item, product, entity_id):
    """The lot named by a dispensation item ({"batch_id"} or {"lote"} - the lot
    number), or None to allocate FEFO/FIFO."""
    if not product.track_batches:
        return None
    if item.get("batch_id"):
        batch = Batch.objects.filter(id=item["batch_id"], product=product, entity_id=entity_id).first()
        if batch is None:
            raise ValidationError("Lot not found.")
        return batch
    if item.get("lote"):
        batch = Batch.objects.filter(lot_number=item["lote"], product=product, entity_id=entity_id).first()
        if batch is None:
            raise ValidationError("Lot not found.")
        return batch
    return None


# =========================================================
# 🛒 INTEGRAÇÃO COM SALES
# =========================================================

@transaction.atomic
def commit_sale_movements(*, sale_id, warehouse_id, items, entity_id, branch_id, user):
    """
    Cria os movimentos de saída referentes à confirmação de uma venda.

    items: iterável de objetos com .product_id e .quantidade (SaleItem).
    Tudo ou nada: se faltar stock nalguma linha, a transação inteira
    é revertida (nenhum movimento fica criado).

    'sales' chama esta função — nunca cria StockMovement diretamente.
    """

    warehouse = _entity_warehouse(warehouse_id, entity_id)

    movimentos = []

    for item in items:
        product = _entity_product(item.product_id, entity_id)
        if product.product_type == Product.TYPE_SERVICE:
            continue  # a service has no stock

        movimentos.extend(issue_stock(
            product=product,
            warehouse=warehouse,
            tipo=StockMovement.TIPO_SAIDA,
            quantidade=Decimal(item.quantidade),
            batch=getattr(item, "batch", None),
            custo_unitario=None,
            documento_origem_tipo="sale",
            documento_origem_id=sale_id,
            entity_id=entity_id,
            branch_id=branch_id,
            user=user,
        ))

    return movimentos


@transaction.atomic
def revert_sale_movements(*, sale_id, warehouse_id, items, entity_id, branch_id, user):
    """
    Cria movimentos de devolução para anular o efeito de stock de uma
    venda confirmada. NUNCA apaga os movimentos originais — o
    livro-razão é append-only.
    """

    # undo the document's own outbound movements, lot by lot ('items' kept
    # for the callers' signature; the movements are the source of truth)
    return reverse_document_movements(
        documento_origem_tipo="sale",
        documento_origem_id=sale_id,
        entity_id=entity_id,
        branch_id=branch_id,
        user=user,
        motivo=f"Anulação da venda {sale_id}",
    )


# =========================================================
# 💊 INTEGRAÇÃO COM FARMACIA
# =========================================================

@transaction.atomic
def commit_dispensation_movements(*, dispensation_id, warehouse_id, items, entity_id, branch_id, user):
    """
    Cria os movimentos de saída referentes a uma dispensação de
    farmácia. Mesma forma que commit_sale_movements, só muda a
    origem do documento — mantém o livro-razão rastreável por tipo
    de operação (ex.: recall de lote -> encontrar movimentos ->
    encontrar dispensações -> identificar pacientes afetados).

    items: iterável de dicts {"product_id": ..., "quantidade": ...}.
    Tudo ou nada: se faltar stock nalguma linha, a transação inteira
    é revertida.

    'farmacia' chama esta função — nunca cria StockMovement
    diretamente nem importa inventory.models.
    """

    warehouse = _entity_warehouse(warehouse_id, entity_id)

    movimentos = []

    for item in items:
        product = _entity_product(item["product_id"], entity_id)
        if product.product_type == Product.TYPE_SERVICE:
            continue  # a service has no stock

        movimentos.extend(issue_stock(
            product=product,
            warehouse=warehouse,
            tipo=StockMovement.TIPO_SAIDA,
            quantidade=Decimal(item["quantidade"]),
            batch=_item_batch(item, product, entity_id),
            custo_unitario=None,
            documento_origem_tipo="dispensation",
            documento_origem_id=dispensation_id,
            entity_id=entity_id,
            branch_id=branch_id,
            user=user,
        ))

    return movimentos


@transaction.atomic
def revert_dispensation_movements(*, dispensation_id, warehouse_id, items, entity_id, branch_id, user):
    """
    Cria movimentos de devolução para anular o efeito de stock de uma
    dispensação anulada. NUNCA apaga os movimentos originais.
    """

    # undo the document's own outbound movements, lot by lot ('items' kept
    # for the callers' signature; the movements are the source of truth)
    return reverse_document_movements(
        documento_origem_tipo="dispensation",
        documento_origem_id=dispensation_id,
        entity_id=entity_id,
        branch_id=branch_id,
        user=user,
        motivo=f"Anulação da dispensação {dispensation_id}",
    )


# =========================================================
# 📥 INTEGRATION WITH PURCHASES
# =========================================================

@transaction.atomic
def commit_purchase_receipt_movements(*, receipt_id, warehouse_id, items, entity_id, branch_id, user):
    """
    Inbound movements of a posted goods receipt (purchases). Same shape as
    commit_sale_movements, with the purchase cost on each movement.

    items: iterable of dicts {"product_id", "quantity", "unit_cost"} and, for a
    product with batch tracking, "lot_number" (required) and "expiry_date".
    Warehouse and products are looked up inside entity_id only - an id of
    another Entity is refused, never moved. All or nothing.

    'purchases' calls this - it never creates StockMovement itself.
    """

    warehouse = _entity_warehouse(warehouse_id, entity_id)

    movements = []

    for item in items:
        product = _entity_product(item["product_id"], entity_id)
        if product.product_type == Product.TYPE_SERVICE:
            continue  # a service has no stock

        batch = None
        if product.track_batches:
            batch = get_or_create_batch(
                product=product, lot_number=item.get("lot_number"), expiry_date=item.get("expiry_date"),
                entity_id=entity_id, branch_id=branch_id, user=user,
            )

        movement, _ = apply_movement(
            product=product,
            warehouse=warehouse,
            tipo=StockMovement.TIPO_ENTRADA,
            quantidade=Decimal(item["quantity"]),
            custo_unitario=item.get("unit_cost"),
            documento_origem_tipo="purchase_receipt",
            documento_origem_id=receipt_id,
            batch=batch,
            entity_id=entity_id,
            branch_id=branch_id,
            user=user,
        )

        movements.append(movement)

    return movements


# =========================================================
# 🔢 CONTAGEM FÍSICA → AJUSTES
# =========================================================

@transaction.atomic
def finalize_inventory_count(*, inventory_count: InventoryCount, user):
    """
    Apura as diferenças de todas as linhas não processadas de uma
    contagem, grava quantidade_sistema/diferenca em cada linha e cria
    um StockMovement de ajuste por cada diferença != 0.

    Motivo do ajuste é obrigatório por definição do movimento — aqui é
    gerado automaticamente a partir da contagem.
    """

    if inventory_count.estado == InventoryCount.ESTADO_CONCLUIDO:
        raise ValidationError("Esta contagem já foi concluída.")

    linhas = (
        inventory_count.linhas
        .select_for_update()
        .filter(processado=False)
    )

    ajustes = []

    for linha in linhas:
        if linha.product.track_batches:
            # a product with lots is counted lot by lot
            if linha.batch_id is None:
                raise ValidationError("A product with lots is counted per lot: the line needs a lot.")
            batch_stock = BatchStock.objects.filter(
                batch_id=linha.batch_id, warehouse=inventory_count.warehouse
            ).first()
            quantidade_sistema = batch_stock.quantity if batch_stock else Decimal("0")
        else:
            stock_item = StockItem.objects.filter(
                product=linha.product,
                warehouse=inventory_count.warehouse
            ).first()
            quantidade_sistema = stock_item.quantidade if stock_item else Decimal("0")
        diferenca = linha.quantidade_contada - quantidade_sistema

        linha.quantidade_sistema = quantidade_sistema
        linha.diferenca = diferenca
        linha.processado = True
        linha.updated_by = user
        linha.save(update_fields=[
            "quantidade_sistema", "diferenca", "processado", "updated_by", "updated_at"
        ])

        if diferenca != 0:
            movement, _ = apply_movement(
                product=linha.product,
                warehouse=inventory_count.warehouse,
                tipo=StockMovement.TIPO_AJUSTE,
                quantidade=diferenca,
                motivo=(
                    f"Ajuste por contagem física #{inventory_count.id} "
                    f"(sistema: {quantidade_sistema}, contado: {linha.quantidade_contada})"
                ),
                documento_origem_tipo="inventory_count",
                documento_origem_id=inventory_count.id,
                batch=linha.batch if linha.product.track_batches else None,
                entity_id=inventory_count.entity_id,
                branch_id=inventory_count.branch_id,
                user=user,
            )
            ajustes.append(movement)

    inventory_count.estado = InventoryCount.ESTADO_CONCLUIDO
    inventory_count.updated_by = user
    inventory_count.save(update_fields=["estado", "updated_by", "updated_at"])

    return ajustes
