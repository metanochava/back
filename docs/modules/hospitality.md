# The `hospitality` module

Bars and restaurants (2026-11-13): the branch's **tables**, their **QR
codes** and what customers ask from them. The same module serves the
**Restaurante** entity type and any entity that activates it (e.g. a shop
with a bar).

It owns no sale and no product. It uses public services:

- `sales.services`: a table's tab is an **open tab** (a named draft sale).
  Calls: `open_tab`, `find_open_tab`, `tab_states`.
- `catalog.services.public_menu`: the menu.

Sales never knows about tables.

## Models

| Model | What |
|---|---|
| `DiningArea` | a part of the branch: room, terrace, bar counter, VIP; unique name per branch |
| `DiningTable` | name (unique per branch), area, seats, order, active; `qr_token` (the QR secret, ~192 bits, read-only); `current_sale_id` (its open tab, read-only) |
| `TableRequest` | what a customer asks from the QR page: `waiter` or `bill`; `open` → `done` with `handled_by` / `handled_at`; **one open request per table and kind** (database constraint) |

## Staff endpoints (PROTECTED, `BaseAPIView`)

| Route | Permission |
|---|---|
| `hospitality/diningareas/`, `hospitality/diningtables/` (CRUD) | `*_diningarea`, `*_diningtable` |
| `GET diningtables/board/`: the branch's active tables with state (`free` / `occupied`), open tab (id, total, lines) and open requests | `board_diningtable` |
| `POST diningtables/{id}/start_tab/` → `{tab}`: the tab it has, else an open tab of the branch with the table's name (adopted), else a new one. The table is locked, so two devices get the same tab. | `start_tab_diningtable` |
| `POST diningtables/{id}/rotate_qr/`: a new secret (the printed QR stops working) | `rotate_qr_diningtable` |
| `GET diningtables/qr_cards/?ids=`: PDF, one A6 card per table (brand colour, logo, table, QR). Reuses `qr_card_service` and `make_brand_qr_b64`. | `qr_cards_diningtable` |
| `hospitality/tablerequests/` (list, read-only), `POST requests/{id}/handle/` (twice changes nothing) | `list_tablerequest`, `handle_tablerequest` |

Ordering, closing and paying a table's tab are the sales tab routes
(`sales.md`, "Open tabs").

## The QR page (PUBLIC)

The QR code opens `<Entity.site>/#/mesa/<qr_token>` (the frontend's hash
router). Without a site the card says to fill it in.

| Route | Answers |
|---|---|
| `GET hospitality/qr/<token>/` | place (name, branch, colour, logo), table, menu by category (active items, base price, image), the open tab's **total and line count only**, the requests waiting |
| `POST hospitality/qr/<token>/call/` `{kind: waiter\|bill}` | 201 new; 202 already waiting (same request) |

Rules:

- The table, and so the Entity, comes **only from the token**.
- An unknown, inactive or rotated token is `404 table_not_found`; so is the
  module inactive for the Entity.
- Throttled per client address: reads `HOSPITALITY_QR_READ_THROTTLE_RATE`
  (600/hour), calls `HOSPITALITY_QR_CALL_THROTTLE_RATE` (30/hour).
- GET never writes.
- No line, customer, cost or token leaves.

`tests/test_access_guard.py` keeps every other view protected; the public one
is listed on purpose.

## Orders from the QR code (2026-11-13)

The customer chooses items on the QR page and sends them with a note; the
order **waits for a member of staff**, so a photographed QR cannot charge
anything.

| Route | What |
|---|---|
| `POST hospitality/qr/<token>/order/` (PUBLIC) `{client_key, lines: [{product_id, quantidade}], note?}` | 201 waiting; 202 the same `client_key` again (same order) |
| `GET hospitality/tableorders/` | the orders (read-only; created by the QR page only) |
| `POST tableorders/{id}/accept/` | puts its lines on the table's tab (opened when it has none) at the catalog's price, through `sales.order_on_tab`; twice changes nothing |
| `POST tableorders/{id}/reject/` | nothing is charged; an accepted order cannot be rejected |

Limits of an order:

- the Entity's **active** catalogued items only;
- whole quantities from 1 to 20, the same item merged;
- at most 20 items;
- at most **3 orders waiting per table**;
- throttled per address (`HOSPITALITY_QR_ORDER_THROTTLE_RATE`, 20/hour).

The QR page shows the table's orders of the last 6 hours with their status.
The point of sale's Tables board shows the waiting orders on each table:
tapping them opens the order to accept or reject.

## Kitchen and bar screens (2026-11-13)

| Model | What |
|---|---|
| `PrepStation` | a station of the branch (Kitchen, Bar) and the catalogue categories it prepares (`category_ids`; catalog stays generic) |
| `PrepTicket` | what a station prepares for one tab: `new` → `preparing` → `ready` → `served` (`new` → `ready` allowed), with the time of each step and who served |
| `PrepTicketLine` | item and quantity |

**How tickets are filled.** Sales emits `sales.tab.ordered` on every order on
a tab (`context`: `sale_id`, `tab_label`, `product_id`, `product_nome`,
`delta`); sales never knows who listens. Hospitality's listener (registered
with `propagate=True`, so the order and its ticket are saved together):

- An item whose category belongs to a station joins that station's **new**
  ticket for the tab; there is one new ticket per station and tab (database
  constraint).
- A unit taken back leaves the new ticket. Once the station started, it is
  already being made.
- Orders after the station started make a new ticket (the next round).
- An item of no station's category gets no ticket.

| Route | Permission |
|---|---|
| `GET hospitality/preptickets/kitchen/?station=` | `kitchen_prepticket` |
| `POST preptickets/{id}/advance/` `{status}` | `advance_prepticket` |
| `hospitality/prepstations/` (CRUD) | `*_prepstation` |

Front:

- **Kitchen and bar** (`KitchenPage.vue`, route `view_kitchen`): a screen
  for a tablet on the wall.
  - Station filter; columns New / Preparing / Ready; big buttons for the
    next step.
  - Minutes waiting, marked red from 15 minutes.
  - Refreshed every 10 s.
- **Preparation stations** (`PrepStationsPage.vue`): each station with its
  categories.

## Profiles (`hospitality/profiles.py`)

| Profile | Gets |
|---|---|
| Waiter (new) | the board, a table's tab, the requests; at the point of sale `checkout_sale` and the lists it needs |
| Cashier | the board, a table's tab, the requests |
| Cook (new) | the stations' screen: see and advance the tickets |
| Bartender (new) | the screen, the tables and the point of sale |
| Hospitality Manager | the above, plus areas, tables, stations, new QR, QR cards and the point of sale |
| Admin | the same as Hospitality Manager |

Action permissions are created by `signals.grant_hospitality_action_permissions`
(post_migrate). The model permissions are created before the profiles.

## Frontend

- **Hospitality menu** (`sidebar.py`): Tables (`TablesPage.vue`, list plus
  "Print QR codes"), Dining areas, Table requests.
- **Point of sale** (`add_sale`): a **Tables** pill with the number of calls
  opens `hospitality/pos/TablesBoard.vue`:
  - tables by area: free, or occupied with the total;
  - blinking when a customer called;
  - tapping a table opens or continues its tab;
  - tapping a call marks it handled.
  - A new call also shows a notice.
  - Shown only with `board_diningtable`.
- **QR page** (`hospitality/qr/TableQrPage.vue`, route `table_qr`
  `/mesa/:token`, public, on every domain): the menu for a phone in the
  brand's colour, with **Call the waiter** / **Ask for the bill** fixed at the
  bottom. Refreshed every 20 s.

## Setup of an environment

1. Add `hospitality` to `MY_APPS`.
2. `makemigrations hospitality`, then `resaas_sync`, then `migrate`.
3. Register the app (`App` name `hospitality`) and link it to the entity
   types / entities that use it.

In dev (2026-11-13):

- the **Restaurante** entity type was created with saas, notifications, hr,
  catalog, inventory, sales, purchases, accounting and hospitality;
- **Venda** and **Tsakane** got hospitality;
- Tsakane got 3 areas (Sala, Esplanada, Balcão) and 15 tables.

## Tests

- `hospitality/tests/test_tables.py`:
  - one tab per table from any device, freed when closed;
  - an open tab with the table's name is adopted;
  - the QR page (menu, total only), and 404 for bad, rotated, inactive or
    module-off tokens;
  - calls once per kind until handled;
  - other Entity, unique names, QR cards PDF, module inactive.
- `test_orders_and_kitchen.py`: QR orders (wait, same key, refused ones, 3 waiting), accept once / reject, tickets per station, taking back, next round, steps, board, other Entity.
- `test_access_guard.py`.
- Front: `TableQrPage.spec.js` and `vendas/sale/SaleSEPage.spec.js` (tables).

Waiter and Cashier also accept / reject the QR orders and see / advance the
tickets (to mark them served).

## Next

- Printing tickets for the stations.
- A visual table map.
- Moving / joining tables.
