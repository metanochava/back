from decimal import Decimal

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.models import Sum

from testutils.tenant import bootstrap_tenant

from inventory import services
from inventory.models import (
    Product, Warehouse, StockItem, StockMovement,
    InventorySetting, InventoryCount, InventoryCountLine,
)


def assert_ledger_matches(testcase, product, warehouse):
    """
    A invariante não-negociável: StockItem.quantidade tem de ser
    exatamente igual à soma de todos os StockMovement do mesmo
    (product, warehouse).
    """

    soma = StockMovement.objects.filter(
        product=product, warehouse=warehouse
    ).aggregate(total=Sum("quantidade"))["total"] or Decimal("0")

    stock_item = StockItem.objects.get(product=product, warehouse=warehouse)

    testcase.assertEqual(stock_item.quantidade, soma)


class LedgerInvariantTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("ledger", modules=("inventory",))

        self.product = Product.objects.create(
            nome="Paracetamol 500mg",
            codigo="PARA-500",
            preco_base=Decimal("10.00"),
            entity=self.tenant["entity"],
            branch=self.tenant["branch"],
            created_by=self.tenant["user"],
            updated_by=self.tenant["user"],
        )

        self.warehouse = Warehouse.objects.create(
            nome="Armazém Central",
            entity=self.tenant["entity"],
            branch=self.tenant["branch"],
            created_by=self.tenant["user"],
            updated_by=self.tenant["user"],
        )

    def _apply(self, tipo, quantidade, **kwargs):
        return services.apply_movement(
            product=self.product,
            warehouse=self.warehouse,
            tipo=tipo,
            quantidade=quantidade,
            entity_id=self.tenant["entity"].id,
            branch_id=self.tenant["branch"].id,
            user=self.tenant["user"],
            **kwargs
        )

    def test_stock_item_equals_sum_of_movements_after_multiple_operations(self):
        self._apply(StockMovement.TIPO_ENTRADA, Decimal("100"))
        self._apply(StockMovement.TIPO_SAIDA, Decimal("-30"))
        self._apply(StockMovement.TIPO_AJUSTE, Decimal("5"), motivo="Correção de contagem")
        self._apply(StockMovement.TIPO_SAIDA, Decimal("-10"))

        assert_ledger_matches(self, self.product, self.warehouse)

        stock_item = StockItem.objects.get(product=self.product, warehouse=self.warehouse)
        self.assertEqual(stock_item.quantidade, Decimal("65"))

    def test_negative_stock_is_blocked_by_default(self):
        self._apply(StockMovement.TIPO_ENTRADA, Decimal("10"))

        with self.assertRaises(ValidationError):
            self._apply(StockMovement.TIPO_SAIDA, Decimal("-50"))

        # o movimento inválido não deve ter ficado gravado (tudo ou nada)
        assert_ledger_matches(self, self.product, self.warehouse)
        stock_item = StockItem.objects.get(product=self.product, warehouse=self.warehouse)
        self.assertEqual(stock_item.quantidade, Decimal("10"))

    def test_negative_stock_allowed_when_entity_settings_permit(self):
        InventorySetting.objects.create(
            entity=self.tenant["entity"],
            branch=self.tenant["branch"],
            allow_negative_stock=True,
            created_by=self.tenant["user"],
            updated_by=self.tenant["user"],
        )

        self._apply(StockMovement.TIPO_SAIDA, Decimal("-20"))

        assert_ledger_matches(self, self.product, self.warehouse)
        stock_item = StockItem.objects.get(product=self.product, warehouse=self.warehouse)
        self.assertEqual(stock_item.quantidade, Decimal("-20"))

    def test_adjustment_requires_motivo(self):
        with self.assertRaises(ValidationError):
            self._apply(StockMovement.TIPO_AJUSTE, Decimal("5"))

    def test_transfer_between_warehouses_is_two_atomic_movements(self):
        destino = Warehouse.objects.create(
            nome="Armazém Secundário",
            entity=self.tenant["entity"],
            branch=self.tenant["branch"],
            created_by=self.tenant["user"],
            updated_by=self.tenant["user"],
        )

        self._apply(StockMovement.TIPO_ENTRADA, Decimal("50"))

        services.transfer_stock(
            product=self.product,
            warehouse_origem=self.warehouse,
            warehouse_destino=destino,
            quantidade=Decimal("20"),
            entity_id=self.tenant["entity"].id,
            branch_id=self.tenant["branch"].id,
            user=self.tenant["user"],
        )

        assert_ledger_matches(self, self.product, self.warehouse)
        assert_ledger_matches(self, self.product, destino)

        origem_item = StockItem.objects.get(product=self.product, warehouse=self.warehouse)
        destino_item = StockItem.objects.get(product=self.product, warehouse=destino)

        self.assertEqual(origem_item.quantidade, Decimal("30"))
        self.assertEqual(destino_item.quantidade, Decimal("20"))

    def test_transfer_fails_atomically_if_origin_has_insufficient_stock(self):
        destino = Warehouse.objects.create(
            nome="Armazém Secundário 2",
            entity=self.tenant["entity"],
            branch=self.tenant["branch"],
            created_by=self.tenant["user"],
            updated_by=self.tenant["user"],
        )

        with self.assertRaises(ValidationError):
            services.transfer_stock(
                product=self.product,
                warehouse_origem=self.warehouse,
                warehouse_destino=destino,
                quantidade=Decimal("10"),
                entity_id=self.tenant["entity"].id,
                branch_id=self.tenant["branch"].id,
                user=self.tenant["user"],
            )

        # nenhum dos dois lados deve ter ficado com movimento parcial
        self.assertFalse(
            StockMovement.objects.filter(product=self.product, warehouse=destino).exists()
        )
        self.assertFalse(
            StockItem.objects.filter(product=self.product, warehouse=self.warehouse).exists()
        )

    def test_finalize_inventory_count_creates_adjustment_matching_difference(self):
        self._apply(StockMovement.TIPO_ENTRADA, Decimal("100"))

        count = InventoryCount.objects.create(
            warehouse=self.warehouse,
            entity=self.tenant["entity"],
            branch=self.tenant["branch"],
            created_by=self.tenant["user"],
            updated_by=self.tenant["user"],
        )

        InventoryCountLine.objects.create(
            inventory_count=count,
            product=self.product,
            quantidade_contada=Decimal("92"),
            entity=self.tenant["entity"],
            branch=self.tenant["branch"],
            created_by=self.tenant["user"],
            updated_by=self.tenant["user"],
        )

        ajustes = services.finalize_inventory_count(
            inventory_count=count,
            user=self.tenant["user"],
        )

        self.assertEqual(len(ajustes), 1)
        self.assertEqual(ajustes[0].quantidade, Decimal("-8"))
        self.assertEqual(ajustes[0].tipo, StockMovement.TIPO_AJUSTE)

        assert_ledger_matches(self, self.product, self.warehouse)

        stock_item = StockItem.objects.get(product=self.product, warehouse=self.warehouse)
        self.assertEqual(stock_item.quantidade, Decimal("92"))

        count.refresh_from_db()
        self.assertEqual(count.estado, InventoryCount.ESTADO_CONCLUIDO)

    def test_sale_commit_then_revert_returns_to_original_balance(self):
        """
        Simula o que 'sales' faria: commit_sale_movements() ao
        confirmar, revert_sale_movements() ao anular. O saldo final
        tem de voltar ao valor original, e o livro-razão nunca é
        apagado (revert cria devolução, não desfaz o commit).
        """

        self._apply(StockMovement.TIPO_ENTRADA, Decimal("100"))

        class FakeItem:
            def __init__(self, product_id, quantidade):
                self.product_id = product_id
                self.quantidade = quantidade

        sale_id = "11111111-1111-1111-1111-111111111111"
        items = [FakeItem(self.product.id, Decimal("15"))]

        services.commit_sale_movements(
            sale_id=sale_id,
            warehouse_id=self.warehouse.id,
            items=items,
            entity_id=self.tenant["entity"].id,
            branch_id=self.tenant["branch"].id,
            user=self.tenant["user"],
        )

        assert_ledger_matches(self, self.product, self.warehouse)
        stock_item = StockItem.objects.get(product=self.product, warehouse=self.warehouse)
        self.assertEqual(stock_item.quantidade, Decimal("85"))

        movimentos_antes = StockMovement.objects.filter(
            product=self.product, warehouse=self.warehouse
        ).count()

        services.revert_sale_movements(
            sale_id=sale_id,
            warehouse_id=self.warehouse.id,
            items=items,
            entity_id=self.tenant["entity"].id,
            branch_id=self.tenant["branch"].id,
            user=self.tenant["user"],
        )

        assert_ledger_matches(self, self.product, self.warehouse)
        stock_item.refresh_from_db()
        self.assertEqual(stock_item.quantidade, Decimal("100"))

        # append-only: o commit original continua lá, o revert é um
        # movimento NOVO, não uma edição/remoção do anterior.
        movimentos_depois = StockMovement.objects.filter(
            product=self.product, warehouse=self.warehouse
        ).count()
        self.assertEqual(movimentos_depois, movimentos_antes + 1)
