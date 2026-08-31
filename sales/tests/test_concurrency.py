import threading
import uuid
from decimal import Decimal

from django.test import TransactionTestCase
from django.db import connection
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType

from testutils.tenant import bootstrap_tenant

from inventory import services as inventory_services
from inventory.models import Product, Warehouse, StockMovement, StockItem

from sales import services as sales_services
from sales.tests.helpers import make_customer, make_sale, make_sale_item


class SalesConcurrencyTests(TransactionTestCase):
    """
    Integração sales -> inventory: duas vendas concorrentes do mesmo
    produto, com stock só para uma, não podem deixar o stock negativo.
    Prova que a integração via inventory.services.commit_sale_movements
    preserva a garantia de concorrência do inventory.
    """

    def tearDown(self):
        ContentType.objects.clear_cache()
        super().tearDown()

    def test_two_concurrent_sale_confirmations_never_oversell_stock(self):
        tenant = bootstrap_tenant("sales-conc", modules=("sales", "inventory"))

        warehouse = Warehouse.objects.create(
            nome="Armazém Vendas",
            entity=tenant["entity"], branch=tenant["branch"],
            created_by=tenant["user"], updated_by=tenant["user"],
        )
        product = Product.objects.create(
            nome="Produto Concorrente Venda", codigo="SCONC-1",
            preco_base=Decimal("10.00"),
            entity=tenant["entity"], branch=tenant["branch"],
            created_by=tenant["user"], updated_by=tenant["user"],
        )

        inventory_services.apply_movement(
            product=product, warehouse=warehouse,
            tipo=StockMovement.TIPO_ENTRADA, quantidade=Decimal("5"),
            entity_id=tenant["entity"].id, branch_id=tenant["branch"].id,
            user=tenant["user"],
        )

        customer = make_customer(tenant)

        sale_1 = make_sale(tenant, customer, warehouse_id=warehouse.id)
        make_sale_item(tenant, sale_1, product_id=product.id, quantidade=Decimal("5"), preco_unitario=Decimal("10.00"))
        sales_services.recalculate_totals(sale_1)

        sale_2 = make_sale(tenant, customer, warehouse_id=warehouse.id)
        make_sale_item(tenant, sale_2, product_id=product.id, quantidade=Decimal("5"), preco_unitario=Decimal("10.00"))
        sales_services.recalculate_totals(sale_2)

        results = []
        results_lock = threading.Lock()

        def confirm(sale_id):
            try:
                from sales.models import Sale
                sale = Sale.objects.get(id=sale_id)
                sales_services.confirm_sale(sale=sale, user=tenant["user"])
                outcome = "ok"
            except ValidationError:
                outcome = "blocked"
            finally:
                connection.close()

            with results_lock:
                results.append(outcome)

        threads = [
            threading.Thread(target=confirm, args=(sale_1.id,)),
            threading.Thread(target=confirm, args=(sale_2.id,)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sorted(results), ["blocked", "ok"])

        stock_item = StockItem.objects.get(product=product, warehouse=warehouse)
        self.assertGreaterEqual(stock_item.quantidade, Decimal("0"))
        self.assertEqual(stock_item.quantidade, Decimal("0"))
