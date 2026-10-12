# The `inventory` module

`inventory` (`back/inventory`) is the generic stock engine and owns the product
catalogue: products and categories, warehouses, stock balances, the stock
ledger (movements), physical counts, lots with expiry, and the inventory
dashboard. It knows nothing about Health or any vertical.

- API: `/api/inventory/<resource>/`, all `BaseAPIView` (PROTECTED).
- Other modules (sales, purchases, pharmacy) use it **only** through
  `inventory/services.py` - never its models - and only when it is installed
  and active for the Entity.

## Ledger rules

- `StockMovement` is append-only; it is created only by
  `services.apply_movement()` (directly or through the functions below), which
  locks the balance row (`select_for_update`) and updates `StockItem` in the
  same transaction. Corrections are new movements (adjustment, return).
- Negative stock is refused unless `InventorySetting.allow_negative_stock` -
  never for products with lots.
- Warehouses and products passed by other modules are looked up **inside the
  Entity** (`_entity_warehouse`, `_entity_product`): another Entity's id is
  refused.

Public functions: `inventory_module_active`, `reserve_stock` (availability, no
movement), `apply_movement`, `issue_stock`, `transfer_stock`,
`get_product_snapshot(product_id, entity_id=None)`, `get_warehouse_snapshot`,
`commit_/revert_sale_movements`, `commit_/revert_dispensation_movements`,
`commit_purchase_receipt_movements`, `get_or_create_batch`,
`allocate_batches`, `reverse_document_movements`, `expiring_batches`,
`finalize_inventory_count`.

## Catalogue: services, variants, price lists

Inventory owns the product catalogue (decision of the horizontal-modules plan:
no separate catalogue app).

**Services.** `Product.product_type` is `goods` (default) or `service`. A service
is sold and bought like a product but **never has stock**: `apply_movement`
refuses it (`A service has no stock.`), and sales, dispensations, purchase
receipts and reservations skip its lines; availability is always true. A
service cannot track lots.

**Variants.** A product can be a variant of another (`variant_of`, with
`variant_attributes`, e.g. `{"Size": "M", "Colour": "Blue"}`); one level only.
The product with variants is a **template**: stock, code and price live on each
variant, and a movement on the template is refused (`Stock is kept on the
variants of this product.`). A product that already has stock cannot get
variants. `product_type` and `track_batches` can only change before the product
has stock movements.

**Price lists.** `PriceList` (`name`, `code` unique per Entity, `valid_from`,
`valid_to`, `active`) and `PriceListItem` (`product`, `min_quantity`, `price` -
quantity breaks). `services.get_price(product_id, entity_id, price_list_id,
quantity, date)` returns the list's price for the highest `min_quantity` ≤
quantity when the list is active and valid on that date, else the product's
`preco_base` (`price_list: null`). API: `/pricelists/`, `/pricelistitems/`,
`GET /products/{id}/price/?price_list=&quantity=` (`price_product`). Pages
**Price lists** and **Prices**.

In sales, a customer can have a price list (`Customer.price_list_id`, checked to
be the Entity's); a sale line sent without `preco_unitario` takes the price from
it (`GET /sales/{id}/preco/?product=&quantidade=`, permission `preco_sale`, used
by the sale page when a product is picked). The point of sale still starts from
the product's base price.

Migrations: `inventory.0004_services_variants_price_lists`,
`sales.0003_customer_price_list`.

## Lots and expiry

Generic (medicines, food, chemicals). A product with **`track_batches`**
("Track lots") keeps its stock per lot:

| Model | What it is |
|---|---|
| `Batch` (lot) | `product`, `lot_number` (unique per product and Entity), `expiry_date`, `manufacture_date`, `notes`. |
| `BatchStock` | Balance of a lot in a warehouse (`quantity` ≥ 0, database check). Read only in the API. |

Invariant: for a product with lots, `StockItem.quantidade` of a warehouse = the
sum of its `BatchStock` there.

Rules (`apply_movement`):

- every movement of such a product names a lot of that product
  (`StockMovement.batch`); a product without lot tracking refuses a lot;
- a lot never goes below zero;
- an **expired** lot cannot leave as an outbound/sale movement (`saida`); it can
  be written off with an adjustment (`ajuste`, reason required).

**Allocation.** When an outbound movement does not name a lot (sales,
dispensations, transfers), `issue_stock()` takes it from the warehouse's lots by
the Entity's `InventorySetting.allocation_strategy`:

- `fefo` (default) - earliest expiry first, lots without expiry last;
- `fifo` - oldest lot first.

Expired lots are never allocated; not enough stock in valid lots refuses the
whole operation. One movement is made per lot used. `reserve_stock()`
(availability) also counts only lots that are not expired.

**Returns** (cancelled sale or dispensation) reverse the document's own
outbound movements, lot by lot (`reverse_document_movements`). **Transfers**
move lot by lot to the destination. **Physical counts** of a product with lots
are per lot: each count line needs `batch`, and the adjustment is made on that
lot.

`track_batches` can only be changed while the product has no stock movements
(`400`).

**Where lots come from.** A goods receipt (`purchases`) asks for the lot number
(required) and expiry date of each line of a product with lots; the lot is
created (or reused - the same number with another expiry date is refused) and
the receipt line keeps them. Lots can also be created in **Lots** and named on a
manual stock movement (`batch`).

**Pharmacy.** A dispensation item names its lot (`lote`, the lot number) or is
allocated FEFO; the lot(s) used are written back on the item.

**Expiring report.** `GET /api/inventory/batches/expiring/?days=30&warehouse=<id>`
(permission `expiring_batch`): lot balances > 0 expiring within `days` or
already expired, with `expired` and `days_left`. Page **Expiring lots**.

Permissions: `list_/view_/add_/change_/delete_batch`, `list_/view_batchstock`,
`expiring_batch`. Inventory Manager manages lots; Inventory Controller,
Warehouse Manager, Storekeeper read them; Receiving Clerk can add them.

Migration: `inventory.0002_lots_and_expiry` (`Product.track_batches`,
`InventorySetting.allocation_strategy`, `Batch`, `BatchStock`,
`StockMovement.batch`, `InventoryCountLine.batch`). Backward compatible:
existing products have lot tracking off and behave as before.

## Stock reservations

`StockReservation` holds stock of a product in a warehouse for a document
(`source_type` + `source_id`, e.g. `sale` + the sale id), with an optional
`expires_at`; status `active`, `consumed` or `released`. Written only by
`inventory/services.py`:

- `reserve()` - under the balance row lock: refused when on hand (valid lots
  only, for products with lots) minus what **other** documents hold is less
  than the quantity (`Not enough available stock to reserve.`). The same
  document, product and warehouse replaces its quantity (idempotent; one active
  reservation per source - database constraint).
- `reserve_document(source_type, source_id, warehouse_id, lines, ...)` - the
  public entry for other modules: releases the document's reservations and
  reserves its current lines, all or nothing.
- `release_reservations()` / `consume_reservations()` - the document gave the
  stock up / took it.

**Availability.** `reserve_stock()` (and the stock balance's `reserved` /
`available` fields) subtract the active reservations; a reservation whose
`expires_at` passed no longer holds anything (no job needed). An outbound or
transfer movement may not take stock reserved for **another** document
(`This stock is reserved for other documents.`); a movement of the document that
holds the reservation can (`documento_origem_tipo` / `_id` = its source).
Adjustments are not limited (they record reality).

**Sales.** `POST /api/sales/sales/{id}/reservar/` (permission `reservar_sale`)
reserves a draft sale's product lines in its warehouse (needs inventory active);
calling it again follows the current lines. Confirming the sale consumes the
reservation; cancelling releases it. Button **Reserve stock** on the sale page.

API: `/api/inventory/stockreservations/` - `GET`, `POST` (a manual reservation:
`product`, `warehouse`, `quantity`, `expires_at`, `reason`; source `manual`),
`POST {id}/release/` (`release_stockreservation`); never edited (`405`). Page
**Stock reservations**. Inventory Manager and Warehouse Manager manage them.

Migration: `inventory.0003_stock_reservations`.

## Tests

`inventory/tests`: ledger invariant, concurrency, tenant isolation, dashboard,
profiles, translations, and `test_lots.py` (lot rules, FEFO with expired and
no-expiry lots, FIFO, expired lot refused, sale and cancellation per lot,
transfer, count per lot, availability, expiry conflict, API, isolation, goods
receipt creating the lot) and `test_reservations.py` (availability, idempotent
reservation, reserved stock protected from other outbound movements, expired
reservation, draft sale reserve/confirm/cancel, API, isolation) and
`test_catalogue.py` (services and templates hold no stock, a sale with a
service moves only the goods, variant rules, price lists with validity and
quantity breaks, sale line price from the customer's price list).
