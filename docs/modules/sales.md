# The `sales` module

`sales` (`back/sales`) is the generic commercial module: customers, sales with
their lines, payments, taxes, and the sales dashboard. It knows nothing about
Health or any vertical.

- API: `/api/sales/<resource>/` (`customers`, `customercontacts`, `sales`,
  `saleitems`, `payments`, `taxes`), all `BaseAPIView` (PROTECTED).
- Frontend: `front/src/pages/vendas` (point of sale, sale page, lists, taxes).

## Sale workflow

`rascunho` (draft) → `confirmada` → `paga`, or `anulada` from any of them.
Totals, status and `stock_tracked` are computed by `sales/services.py`, never
accepted from the client. Lines can be changed only while the sale is a draft.

| Action | Route | Permission |
|---|---|---|
| Stock availability | `GET /sales/{id}/disponibilidade/` | `disponibilidade_sale` |
| Confirm | `POST /sales/{id}/confirmar/` | `confirmar_sale` |
| Cancel | `POST /sales/{id}/anular/` | `anular_sale` |
| Payment | `POST /sales/{id}/pagar/` (`valor`, `forma_pagamento`, `referencia`) | `pagar_sale` |
| Reserve stock (draft) | `POST /sales/{id}/reservar/` - see [inventory reservations](inventory.md#stock-reservations) | `reservar_sale` |

Events emitted (for other modules, e.g. accounting - sales never knows who
listens): `sales.sale.confirmed` and `sales.sale.cancelled` (`context.amount` =
total), `sales.payment.received` (`amount`, `sale_id`, `method`).

## Inventory is optional

`sales` uses `inventory.services` only when the `inventory` app is installed
**and** the module is active for the Entity (`sales.services.inventory()` /
`stock_enabled()`):

| Situation | Behaviour |
|---|---|
| inventory active, sale has a warehouse | confirming moves stock out for the **product lines** (`stock_tracked=true`); cancelling returns it |
| no warehouse, or inventory inactive | the sale works, no stock moves (`stock_tracked=false`) |
| inventory not installed | as above; a `product_id` or `warehouse_id` cannot be validated, so they are refused (`400`) |

A line is either an inventory product (`product_id`; its `product_nome` /
`product_codigo` are a snapshot taken from inventory, whatever the client sent)
or a **free line** with only `product_nome` as its description (a service). A
line with neither is `400`. Free lines never move stock.

Tenant scope: `product_id` must be one of the Entity's products and
`warehouse_id` one of its warehouses (`400` otherwise). The inventory functions
`commit_sale_movements` / `revert_sale_movements` (and the pharmacy's
`commit_dispensation_movements`) look the warehouse and products up inside the
Entity again and refuse another Entity's ids.

## Prices

A product line sent without `preco_unitario` gets the price of the customer's
price list (`Customer.price_list_id`), else the product's base price - see
[inventory price lists](inventory.md#catalogue-services-variants-price-lists).
A line of a service product never moves stock.

## Taxes

`Tax` (`/api/sales/taxes/`): `name`, `code` (unique per Entity), `rate`
(percentage 0-100), `active`. The Entity configures its own taxes; no country's
rules are built in.

A sale line may have a `tax`. When the line is written, the tax's rate is
**copied** to `SaleItem.tax_rate` (read only in the API), so changing or
deactivating a tax never changes past sales. Per line:

```
subtotal   = quantidade × preco_unitario − desconto_valor
tax_amount = subtotal × tax_rate / 100, rounded to cents (half up)
```

The sale keeps `subtotal`, `desconto_total`, `tax_total` and
`total = subtotal − desconto_total + tax_total`. An inactive tax, or another
Entity's, is refused (`400`); a tax already used cannot be deleted
(`409 tax_in_use`) - make it inactive.

Frontend: the point of sale offers one optional tax for the cart and shows it
in the totals (the amount charged is the backend total returned by confirm);
the sale page lets each line have its own tax and a description instead of a
product; **Taxes** (`list_tax`) is a schema-driven list.

Permissions: `list_/view_/add_/change_/delete_tax`; Sales Manager manages
taxes, Sales Representative, Cashier and Accountant can read them.

## Migrations

`sales.0002_taxes_and_optional_product`: adds `Tax`, `SaleItem.tax` /
`tax_rate`, `Sale.tax_total`, and makes `SaleItem.product_id` optional.
Backward compatible: existing lines keep their product and get rate 0.

## Tests

`sales/tests`: totals, state machine, concurrency, tenant isolation,
dashboard, profiles, translations, and `test_taxes_and_optional_inventory.py`
(tax copy and totals, inactive/foreign tax, free lines, product and warehouse
scope, only product lines move stock, sales without the inventory app).
