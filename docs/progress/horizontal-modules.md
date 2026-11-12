# Progress: horizontal modules

Plan approved on 2026-10-11. New horizontal modules live in this application
(`back/<module>`, `front/src/pages/<module>`), next to `inventory` and `sales`;
framework fixes go to `django_resaas`.

| Phase | Scope | State |
|---|---|---|
| 1 | `Document` scoped per Entity (django_resaas `0004_document_entity_scope`) | Done |
| 1b | Media files: tokens bound to their path, `/media/` through Django + `X-Accel-Redirect` | Done in dev; production pending release |
| 2 | Purchases - [docs/modules/purchases.md](../modules/purchases.md) | Done in dev |
| 3 | Accounting - [docs/modules/accounting.md](../modules/accounting.md) | Done in dev |
| 4 | Sales without a hard dependency on Inventory; taxes - [docs/modules/sales.md](../modules/sales.md) | Done in dev |
| 5 | CRM - [docs/modules/crm.md](../modules/crm.md) | Done in dev |
| 6 | Workflow (approvals) - [docs/modules/workflow.md](../modules/workflow.md) | Done in dev |
| 7a | Lots and expiry (FEFO/FIFO) - [docs/modules/inventory.md](../modules/inventory.md) | Done in dev |
| 7b | Stock reservations - [docs/modules/inventory.md](../modules/inventory.md#stock-reservations) | Done in dev |
| 7c | Services, variants, price lists - [docs/modules/inventory.md](../modules/inventory.md#catalogue-services-variants-price-lists) | Done in dev |

## Decisions

- Catalogue: `Product` stays in `inventory`, which owns the catalogue (option a).
- A horizontal module that uses another one goes through its `services.py` and
  only when installed and active (purchases → inventory).
- Cross-module references are loose UUIDs validated inside the Entity, never
  foreign keys between modules.
- Integration between modules goes through `EventDispatcher` events carrying
  `context.amount`; sales now emits `sales.sale.confirmed`, `sales.sale.cancelled`
  and `sales.payment.received`.

## Known issues

- The point of sale (POS) starts lines from the product's base price, not the
  customer's price list.

- Automatic accounting entries post the sale total to one credit account; a
  separate tax account (split entry) is not supported yet.
- `ThemeSurface.background_image` and the bootstrap e-mail logo return an
  unsigned media URL (no request to sign with); they answer `401` once `/media/`
  goes through Django. No data uses them today.

## Catalog, Inventory, Sales, Health and Form Engine (initiative of 2026-11-11)

### Phase 0 - audit (2026-11-11)

Initial state: django_resaas 0.0.684 (develop, clean), quasar_resaas 0.0.1492
(main), back 1.0.112 (develop), front 0.0.92 (main). The local changes in
quasar_resaas, back and front are earlier uncommitted work (reprint, change_
right menus, route scroll in every layout, booking times) - not part of this
initiative.

| Area | What exists | Gap |
|---|---|---|
| Catalogue | (before phase 2) In `inventory`: `Product` (`product_type` goods/service, `variant_of` + `variant_attributes`, `codigo`, `unidade`, `preco_base`), `ProductCategory`, `ProductMedia`, `PriceList`, `PriceListItem`, `get_price()` | Lives inside inventory (decision of 2026-10-11): without inventory there is no catalogue of services - "Catalog + Sales without Inventory" and "hotel without Health" have only free sale lines. No barcode/SKU separate from `codigo`, no units of measure model |
| Inventory | `Warehouse`, `StockItem`, `StockMovement`, `Batch`, `BatchStock`, `StockReservation`, `InventoryCount(Line)`, `InventorySettings`; FEFO/FIFO, reservations, counts, reversals, no negative stock; services only (`services.py`, 1107 lines) | Consumes its own `Product`; would consume the catalog's |
| Sales | `Sale`, `SaleItem` (loose `product_id` + name/code snapshot), `Payment`, `Customer` (`price_list_id`), `Tax`; inventory optional (`inventory()` / `stock_enabled()`), free lines for services; events `sales.sale.confirmed/cancelled`, `sales.payment.received` | `create_sale()` refuses any `product_id` without inventory ("The inventory module is required to sell products") - a catalogued service cannot be sold without inventory |
| Pharmacy | `MedicineCatalogItem` / `MedicineCatalogMedia` (platform catalogue), `PharmacyOffer` (loose `product_id`), dispensation through `inventory.services.commit_dispensation_movements` | Global ↔ local link to review once the catalog is its own module |
| Health | Clinical models only | No link at all to sales or inventory (no charging of consultations/exams, no material consumption) |
| References | `product_id` in sales, purchases, farmacia (`produto_id`, `product_id`) are loose UUIDs, never FKs; horizontal modules import no vertical one | - |
| Form engine | Schema 1.0 automatic forms (`AutoForm`, `FormTwo`, `FormComponent`, `ActionForm`, `FormSection`, `FieldComponent`, `utils/schema.js` `guessComponent`, `utils/autoForm.js` rules); dashboards already have a component registry (`components/dashboard/registry.js`) | No declarative definitions, no condition DSL, no component registry for forms, no PLATFORM → ENTITY TYPE → ENTITY → BRANCH configuration, no backend form definition model |
| Events | `EventDispatcher` (`saas/core/events`), lifecycle events, notifications outbox | No outbox for domain events between modules |

Tests today: 181 in inventory + sales + farmacia.

### Phase 1 - decided 2026-11-11

The owner chose: catalog as its own module; order Catalog → Sales → Health
(the Form Engine after); the earlier uncommitted work committed separately
(done, local only).

### Phase 2 - Catalog (2026-11-11/12, dev)

Done in dev, see [catalog.md](../modules/catalog.md): `back/catalog` with the
five models (same tables and ids), `catalog.services`, menu, profiles,
translations, compatibility names and routes in inventory; frontend on
`/api/catalog/`. Dev DB backed up (`backups/dev-20261111-2359-before-catalog.dump`)
and migrated: 40 products kept, ContentTypes and permissions in catalog,
catalog active for 7 Entities. Production: inventory's state migration must
be written by hand (see catalog.md).

Proposal kept from phase 1:

Catalog as its own horizontal module (`back/catalog`), reversing the
2026-10-11 decision because it is what makes Catalog + Sales work without
Inventory. Safe because no other module holds a foreign key to `Product`:

- `catalog` takes `Product`, `ProductCategory`, `ProductMedia`, `PriceList`,
  `PriceListItem` with `SeparateDatabaseAndState` migrations: same tables
  (`db_table` kept), same ids, no data copied; inventory's own FKs point to
  `catalog.Product`.
- `catalog.services` (public): product snapshot, price, "is it stocked".
  inventory and sales use it; inventory keeps its current functions as
  compatibility wrappers while anything calls them.
- sales accepts a catalog `product_id` without inventory; stock moves only
  for stocked goods when inventory is active.
- Health: links clinical services to catalog items (a mapping model in
  saude, loose ids), charging through sales services when the act is
  performed; dispensation and material consumption through inventory
  services. No clinical model moves.
- Form Engine in the libraries (transversal): a backend form definition
  model with versioning and PLATFORM → ENTITY TYPE → ENTITY → BRANCH
  precedence, a limited JSON condition DSL (no eval), and a frontend
  renderer + component registry over the existing s-* fields, keeping
  Schema 1.0.
