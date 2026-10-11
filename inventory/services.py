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
    - revert_dispensation_movements(dispensation, user)
    - finalize_inventory_count(inventory_count, user)

Outros módulos (sales, farmacia, ...) só devem importar deste
ficheiro — nunca importar models do inventory diretamente para
escrever dados.
"""

import uuid
from decimal import Decimal

from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError

from django_resaas.saas.models.app import App
from django_resaas.saas.models.entity_app import EntityApp

from inventory.models import (
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


# =========================================================
# 📖 DISPONIBILIDADE (SEM CRIAR MOVIMENTO)
# =========================================================

def reserve_stock(lines, *, warehouse_id, entity_id):
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

    resultado = []

    for line in lines:
        disponivel = saldo_por_produto.get(line["product_id"], Decimal("0"))
        pedida = Decimal(line["quantidade"])

        resultado.append({
            "product_id": line["product_id"],
            "quantidade_pedida": pedida,
            "quantidade_disponivel": disponivel,
            "disponivel": allow_negative or disponivel >= pedida,
        })

    return resultado


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
):
    """
    Cria um StockMovement e atualiza o StockItem correspondente na
    mesma transação, com lock de linha (select_for_update) para
    evitar corrida entre operações concorrentes sobre o mesmo
    (product, warehouse).
    """

    quantidade = Decimal(quantidade)

    if quantidade == 0:
        raise ValidationError("Quantidade do movimento não pode ser zero.")

    if tipo == StockMovement.TIPO_AJUSTE and not motivo:
        raise ValidationError("Motivo é obrigatório para movimentos de ajuste.")

    stock_item = _lock_stock_item(
        product=product,
        warehouse=warehouse,
        entity_id=entity_id,
        branch_id=branch_id,
        user=user,
    )

    novo_saldo = stock_item.quantidade + quantidade

    if novo_saldo < 0 and not _allow_negative_stock(entity_id):
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
        entity_id=entity_id,
        branch_id=branch_id,
        created_by=user,
        updated_by=user,
    )

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
):
    quantidade = Decimal(quantidade)

    if quantidade <= 0:
        raise ValidationError("Quantidade de transferência deve ser positiva.")

    if warehouse_origem.id == warehouse_destino.id:
        raise ValidationError("Armazém de origem e destino não podem ser iguais.")

    ref_id = uuid.uuid4()

    saida, _ = apply_movement(
        product=product,
        warehouse=warehouse_origem,
        tipo=StockMovement.TIPO_TRANSFERENCIA,
        quantidade=-quantidade,
        motivo=motivo,
        documento_origem_tipo="transferencia",
        documento_origem_id=ref_id,
        entity_id=entity_id,
        branch_id=branch_id,
        user=user,
    )

    entrada, _ = apply_movement(
        product=product,
        warehouse=warehouse_destino,
        tipo=StockMovement.TIPO_TRANSFERENCIA,
        quantidade=quantidade,
        motivo=motivo,
        documento_origem_tipo="transferencia",
        documento_origem_id=ref_id,
        entity_id=entity_id,
        branch_id=branch_id,
        user=user,
    )

    return saida, entrada


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

    warehouse = Warehouse.objects.get(id=warehouse_id)

    movimentos = []

    for item in items:
        product = Product.objects.get(id=item.product_id)

        movement, _ = apply_movement(
            product=product,
            warehouse=warehouse,
            tipo=StockMovement.TIPO_SAIDA,
            quantidade=-Decimal(item.quantidade),
            custo_unitario=None,
            documento_origem_tipo="sale",
            documento_origem_id=sale_id,
            entity_id=entity_id,
            branch_id=branch_id,
            user=user,
        )

        movimentos.append(movement)

    return movimentos


@transaction.atomic
def revert_sale_movements(*, sale_id, warehouse_id, items, entity_id, branch_id, user):
    """
    Cria movimentos de devolução para anular o efeito de stock de uma
    venda confirmada. NUNCA apaga os movimentos originais — o
    livro-razão é append-only.
    """

    warehouse = Warehouse.objects.get(id=warehouse_id)

    movimentos = []

    for item in items:
        product = Product.objects.get(id=item.product_id)

        movement, _ = apply_movement(
            product=product,
            warehouse=warehouse,
            tipo=StockMovement.TIPO_DEVOLUCAO,
            quantidade=Decimal(item.quantidade),
            motivo=f"Anulação da venda {sale_id}",
            documento_origem_tipo="sale",
            documento_origem_id=sale_id,
            entity_id=entity_id,
            branch_id=branch_id,
            user=user,
        )

        movimentos.append(movement)

    return movimentos


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

    warehouse = Warehouse.objects.get(id=warehouse_id)

    movimentos = []

    for item in items:
        product = Product.objects.get(id=item["product_id"])

        movement, _ = apply_movement(
            product=product,
            warehouse=warehouse,
            tipo=StockMovement.TIPO_SAIDA,
            quantidade=-Decimal(item["quantidade"]),
            custo_unitario=None,
            documento_origem_tipo="dispensation",
            documento_origem_id=dispensation_id,
            entity_id=entity_id,
            branch_id=branch_id,
            user=user,
        )

        movimentos.append(movement)

    return movimentos


@transaction.atomic
def revert_dispensation_movements(*, dispensation_id, warehouse_id, items, entity_id, branch_id, user):
    """
    Cria movimentos de devolução para anular o efeito de stock de uma
    dispensação anulada. NUNCA apaga os movimentos originais.
    """

    warehouse = Warehouse.objects.get(id=warehouse_id)

    movimentos = []

    for item in items:
        product = Product.objects.get(id=item["product_id"])

        movement, _ = apply_movement(
            product=product,
            warehouse=warehouse,
            tipo=StockMovement.TIPO_DEVOLUCAO,
            quantidade=Decimal(item["quantidade"]),
            motivo=f"Anulação da dispensação {dispensation_id}",
            documento_origem_tipo="dispensation",
            documento_origem_id=dispensation_id,
            entity_id=entity_id,
            branch_id=branch_id,
            user=user,
        )

        movimentos.append(movement)

    return movimentos


# =========================================================
# 📥 INTEGRATION WITH PURCHASES
# =========================================================

@transaction.atomic
def commit_purchase_receipt_movements(*, receipt_id, warehouse_id, items, entity_id, branch_id, user):
    """
    Inbound movements of a posted goods receipt (purchases). Same shape as
    commit_sale_movements, with the purchase cost on each movement.

    items: iterable of dicts {"product_id", "quantity", "unit_cost"}.
    Warehouse and products are looked up inside entity_id only - an id of
    another Entity is refused, never moved. All or nothing.

    'purchases' calls this - it never creates StockMovement itself.
    """

    warehouse = Warehouse.objects.filter(id=warehouse_id, entity_id=entity_id).first()
    if warehouse is None:
        raise ValidationError("Warehouse not found.")

    movements = []

    for item in items:
        product = Product.objects.filter(id=item["product_id"], entity_id=entity_id).first()
        if product is None:
            raise ValidationError("Product not found.")

        movement, _ = apply_movement(
            product=product,
            warehouse=warehouse,
            tipo=StockMovement.TIPO_ENTRADA,
            quantidade=Decimal(item["quantity"]),
            custo_unitario=item.get("unit_cost"),
            documento_origem_tipo="purchase_receipt",
            documento_origem_id=receipt_id,
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
                entity_id=inventory_count.entity_id,
                branch_id=inventory_count.branch_id,
                user=user,
            )
            ajustes.append(movement)

    inventory_count.estado = InventoryCount.ESTADO_CONCLUIDO
    inventory_count.updated_by = user
    inventory_count.save(update_fields=["estado", "updated_by", "updated_at"])

    return ajustes
