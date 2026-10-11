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
| 4 | Sales without a hard dependency on Inventory; taxes | Next |
| 5 | CRM (leads, opportunities, stages, activities) | Planned |
| 6 | Workflow (definitions, steps, approvals; registered actions only) | Planned |
| 7 | Catalogue/Inventory: variants, price lists, services, lots, expiry, reservations | Planned |

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

- `inventory.services.commit_sale_movements` / `commit_dispensation_movements`
  look warehouses and products up without the Entity (sales/farmacia pass ids
  from their own records); to be scoped in phase 4.
- `ThemeSurface.background_image` and the bootstrap e-mail logo return an
  unsigned media URL (no request to sign with); they answer `401` once `/media/`
  goes through Django. No data uses them today.
