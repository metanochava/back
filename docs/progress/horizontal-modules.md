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
