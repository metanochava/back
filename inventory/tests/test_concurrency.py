import threading
from decimal import Decimal

from django.test import TransactionTestCase
from django.db import connection
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType

from testutils.tenant import bootstrap_tenant

from inventory import services
from inventory.models import Product, Warehouse, StockItem, StockMovement


class ConcurrencyTests(TransactionTestCase):
    """
    Requisito não-negociável: venda concorrente do mesmo produto não
    pode gerar stock negativo indevido. Usa TransactionTestCase (em
    vez de TestCase) porque select_for_update() só bloqueia entre
    conexões/transações reais — o TestCase normal envolve o teste
    todo numa única transação por savepoints, o que mascararia
    qualquer corrida.
    """

    def tearDown(self):
        # Evita que ContentType.objects.get_for_model() devolva um id
        # em cache que deixou de existir depois do flush automático
        # do TransactionTestCase (que corre a seguir a este tearDown)
        # — sem isto, o post_migrate re-disparado pelo flush pode
        # tentar gravar auth_permission com um content_type_id morto.
        ContentType.objects.clear_cache()
        super().tearDown()

    def test_two_concurrent_sales_for_the_same_stock_never_go_negative(self):
        tenant = bootstrap_tenant("concurrency", modules=("inventory",))

        warehouse = Warehouse.objects.create(
            nome="Armazém Concorrência",
            entity=tenant["entity"],
            branch=tenant["branch"],
            created_by=tenant["user"],
            updated_by=tenant["user"],
        )

        product = Product.objects.create(
            nome="Produto Concorrente",
            codigo="CONC-1",
            preco_base=Decimal("1.00"),
            entity=tenant["entity"],
            branch=tenant["branch"],
            created_by=tenant["user"],
            updated_by=tenant["user"],
        )

        # Só há stock suficiente para UMA das duas vendas concorrentes.
        services.apply_movement(
            product=product,
            warehouse=warehouse,
            tipo=StockMovement.TIPO_ENTRADA,
            quantidade=Decimal("10"),
            entity_id=tenant["entity"].id,
            branch_id=tenant["branch"].id,
            user=tenant["user"],
        )

        results = []
        results_lock = threading.Lock()

        def sell():
            try:
                services.apply_movement(
                    product=product,
                    warehouse=warehouse,
                    tipo=StockMovement.TIPO_SAIDA,
                    quantidade=Decimal("-10"),
                    entity_id=tenant["entity"].id,
                    branch_id=tenant["branch"].id,
                    user=tenant["user"],
                )
                outcome = "ok"
            except ValidationError:
                outcome = "blocked"
            finally:
                connection.close()

            with results_lock:
                results.append(outcome)

        threads = [threading.Thread(target=sell) for _ in range(2)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # exatamente uma venda passa, a outra é bloqueada por falta de stock
        self.assertEqual(sorted(results), ["blocked", "ok"])

        stock_item = StockItem.objects.get(product=product, warehouse=warehouse)
        self.assertGreaterEqual(stock_item.quantidade, Decimal("0"))
        self.assertEqual(stock_item.quantidade, Decimal("0"))

        soma = StockMovement.objects.filter(
            product=product, warehouse=warehouse
        ).aggregate(total=Sum("quantidade"))["total"]

        self.assertEqual(stock_item.quantidade, soma)
