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

## Point of sale (checkout)

Route `add_sale` (`front/src/pages/vendas/sale/SaleSEPage.vue`). The cart
lives in the browser only; **Finish Sale** sends it in one request and the
payments follow (2026-11-13).

| Action | Route | Permission |
|---|---|---|
| Price of a line | `GET /sales/quote/?product=&quantidade=&customer=` → `{price, price_list}` | `checkout_sale` |
| Payment methods | `GET /sales/payment_methods/` → `[{value, label}]` (`Payment.FORMA_CHOICES`) | `checkout_sale` |
| Checkout | `POST /sales/checkout/` `{checkout_key, lines: [{product_id, quantidade, desconto_valor?}], customer?, warehouse_id?, tax?, observacao?}` | `checkout_sale` |

`services.checkout_sale()` creates the sale, its lines and confirms it in one
transaction (stock moves on confirmation, as always):

- **The price is always the catalog's** for the customer (`services.quote()`:
  their price list and its quantity breaks, else the base price). A price sent
  by the client is never read.
- **A discount needs `discount_sale`** (403 without it), never negative and
  never more than the line.
- **One optional tax** for the whole cart: the Entity's and active.
- **Idempotent:** `checkout_key` (a UUID per cart, `Sale.checkout_key`, unique
  per Entity) returns the sale that key already created (`202`, the POST
  convention for an existing result) instead of a second one (`201`). The page keeps the key while the cart is the same (a
  retry after a network error) and makes a new one when the cart changes.
- **All or nothing:** an unknown or another Entity's product, customer or tax,
  a quantity of zero or a bad number is `400` and leaves no sale behind.

The page shows each line at the quoted price, sends no prices, pays the
server's total (split between methods, change in cash) and voids the
confirmed sale on **Cancel Sale**.

Profiles (`sales/profiles.py`, `POINT_OF_SALE`: `checkout_sale`, `pagar_sale`,
`list_customer`, `list_product`, `list_warehouse`):

| Profile | Point of sale |
|---|---|
| Cashier | sells, takes payments, voids (`anular_sale`) |
| Sales Representative | sells, takes payments |
| Sales Manager, Admin | the above, voids and gives discounts (`discount_sale`) |

Before this, Cashier and Sales Manager had neither `confirmar_sale` nor
`pagar_sale` and could not finish a sale at the point of sale.

## Open tabs (bar, restaurant)

The point of sale serves several customers at once: each **tab** is a draft
sale with a name (`Sale.tab_label`: a table or a person) that the branch's
devices add orders to until it is closed and paid (2026-11-13). Every route
answers the tab with its lines.

| Action | Route | Permission |
|---|---|---|
| The branch's open tabs | `GET /sales/open_tabs/` (total, `line_count`, oldest first) | `checkout_sale` |
| Open a tab | `POST /sales/open_tab/` `{tab_label, customer?, warehouse_id?}` | `checkout_sale` |
| A tab with its lines | `GET /sales/{id}/tab/` | `checkout_sale` |
| Order / take back | `POST /sales/{id}/order/` `{product_id, delta}` (`delta` 1 by default, negative takes back) | `checkout_sale` |
| A line's discount | `POST /sales/{id}/discount/` `{item, desconto_valor}` | `discount_sale` |
| Split ("each pays theirs") | `POST /sales/{id}/split/` `{items: [{item, quantidade}], tab_label?}` → 201 the new tab | `checkout_sale` |
| Close (then pay with `pagar`) | `POST /sales/{id}/close/` `{tax?, warehouse_id?}` | `checkout_sale` |
| Void | `POST /sales/{id}/anular/` | `anular_sale` |

Rules (`services.open_tab`, `order_on_tab`, `discount_on_tab`, `split_tab`,
`close_tab`):

- **One open tab per name in a branch** (database constraint
  `unique_open_tab_label_per_branch`); a closed tab frees its name.
- **The price is the catalog's** for the tab's customer, re-priced for the
  line's quantity on every order. A line reaching zero is removed.
- **Orders on the same tab are serialised** (the tab is locked), so two
  devices ordering at once both count.
- **Every order emits `sales.tab.ordered`** (`sale_id`, `tab_label`,
  `product_id`, `product_nome`, `delta`); e.g. hospitality's kitchen screens
  listen to it. Sales never knows who listens.
- **A closed or voided tab takes nothing more:** `409 tab_not_open`.
- **Closing twice confirms once:** the second close answers the closed sale.
  Closing applies the optional tax to every line and confirms the sale (stock
  moves now). An empty tab cannot be closed.
- **Splitting** moves whole lines (with their discount) or part of a line (at
  the same unit price) to a new tab named after the old one (`Table 4 (2)`).
- Every member of the branch with `checkout_sale` sees every open tab.

**Page** (`SaleSEPage.vue` and `sale/pos/`), made for a phone or a tablet:

- the tabs as pills that scroll sideways, with **Quick sale** (the one-request
  checkout above) and **New tab**; a tab open for more than 3 hours is
  marked;
- the products as big tiles (image or coloured initials), with search,
  barcode (typed, scanner or camera) and category chips;
- the cart beside the products from a tablet in landscape up, a bottom bar
  that opens it on a phone;
- the tabs refresh every 15 seconds and when the screen comes back, so every
  device sees the same tabs;
- payment split between the backend's methods, change in cash, then the
  receipt. Cancelling the payment voids the confirmed sale.

## Catalog and Inventory are optional

What is sold comes from **catalog** (goods and services); stock from
**inventory**. `sales` uses each one's public services only when the app is
installed **and** the module is active for the Entity, never their models
(`sales.services.catalog()` / `catalog_enabled()`, `inventory()` /
`stock_enabled()`):

| Situation | Behaviour |
|---|---|
| catalog active | a line can be one of the Entity's catalogued goods or services (`product_id`): its `product_nome` / `product_codigo` are a snapshot from the catalog, whatever the client sent, and its price (when not sent) the customer's price list, else the base price |
| catalog inactive | only free lines (`product_nome` as description); a `product_id` is `400` and `create_sale()` refuses |
| inventory active, sale has a warehouse | confirming moves stock out for the **goods** lines (`stock_tracked=true`); a service never holds stock; cancelling returns it |
| no warehouse, or inventory inactive / not installed | the sale works, no stock moves (`stock_tracked=false`); a `warehouse_id` cannot be validated without inventory, so it is `400` |

Activating inventory, sales, purchases or farmacia for an Entity activates the
catalog too (`catalog/signals.py`, `settings.CATALOG_CONSUMER_MODULES`). A
doctor's office or a hotel sells catalogued services (and goods without stock
control) with Catalog + Sales only. The point of sale shows the warehouse only
to who may list warehouses.

The line keeps its snapshot (name, code, quantity, price, tax rate) whatever
happens to the catalogued item afterwards. A line with neither `product_id`
nor `product_nome` is `400`.

Tenant scope: `product_id` must be one of the Entity's catalogued items and
`warehouse_id` one of its warehouses (`400` otherwise). The inventory functions
`commit_sale_movements` / `revert_sale_movements` (and the pharmacy's
`commit_dispensation_movements`) look the warehouse and products up inside the
Entity again and refuse another Entity's ids.

## Public services for other modules

Modules that bill someone (Health, academica) use `sales/services.py`, never the
models: `customer_for_person()` (the Entity's customer for a Person, made once),
`create_sale(customer_id=...)`, `sales_module_active()` and
`get_sale_snapshots(sale_ids, entity_id)`. The last one is read-only and
returns `{sale_id: {id, estado, data, total, paid, balance}}` for the Entity's
sales only, so a module can show what is paid and owed (the academica portal's
fees). Deleted payments do not count, a voided sale owes nothing, and another
Entity's ids are simply missing.

For open tabs (e.g. the tables of `hospitality`): `open_tab()`,
`find_open_tab(entity_id, branch_id, label)` (the branch's open tab with that
name, or `None`), `get_open_tab(sale_id, entity_id)` and `tab_states(sale_ids, entity_id)` →
`{sale_id: {open, estado, total, line_count}}`, read-only, another Entity's
ids missing.

Tests: `sales/tests/test_catalog_sales.py` (office without inventory, hotel
without Health, mixed sale with stock, partial payments, snapshot, catalog
inactive), `test_taxes_and_optional_inventory.py`.

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
in the totals (the amount charged is the backend total returned by checkout);
the sale page lets each line have its own tax and a description instead of a
product; **Taxes** (`list_tax`) is a schema-driven list.

Permissions: `list_/view_/add_/change_/delete_tax`; Sales Manager manages
taxes, Sales Representative, Cashier and Accountant can read them.

## Migrations

`sales.0002_taxes_and_optional_product`: adds `Tax`, `SaleItem.tax` /
`tax_rate`, `Sale.tax_total`, and makes `SaleItem.product_id` optional.
Backward compatible: existing lines keep their product and get rate 0.

`Sale.checkout_key` (nullable UUID, unique per Entity when set) and the
`discount_sale` permission: additive, existing sales keep `null`. sales'
migrations are generated per environment (`makemigrations sales`, then
`resaas_sync` and `migrate`); `create_sales_groups` creates the model
permissions before applying the profiles, so `discount_sale` is granted on the
first `migrate`.

`sales.0005`: `Sale.tab_label` (nullable) and the open-tab name constraint.
Additive; existing sales have no name.

## Tests

`sales/tests`: totals, state machine, concurrency, tenant isolation,
dashboard, profiles, translations, and `test_taxes_and_optional_inventory.py`
(tax copy and totals, inactive/foreign tax, free lines, product and warehouse
scope, only product lines move stock, sales without the inventory app).
`test_checkout.py`: the catalog / price-list price, idempotency, nothing left
after a bad line, discount and tax, the discount and checkout permissions,
tenant isolation, split payments. `test_tabs.py`: orders at the catalog
price, taking back, one open tab per name, close once, empty tab, split,
discount permission, voided tab, orders counted, other branch / Entity.
Front: `SaleSEPage.spec.js` (quick sale and tabs).
