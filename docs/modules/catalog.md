# The `catalog` module

`catalog` (`back/catalog`) is the commercial identity of what an Entity sells
or buys: goods and services, categories, variants, media and price lists. It
is horizontal: it knows nothing about stock (`inventory`), sales (`sales`) or
any vertical (`saude`, `farmacia`, ...). Other modules read it through
`catalog.services` and keep **loose product ids** (never foreign keys between
modules).

- API: `/api/catalog/<resource>/` - `products`, `productcategorys`,
  `productmedias`, `pricelists`, `pricelistitems`, all `BaseAPIView`
  (PROTECTED; module `catalog` active for the Entity). `GET
  products/{id}/price/?price_list=&quantity=` (`price_product`).
- Menu "Catalog" (`catalog/sidebar.py`): Products, Product Categories, Price
  lists, Prices. Frontend pages: `front/src/pages/stock/{product,
  productcategory, productmedia, pricelist}` (stores and crud pages use
  `app: 'catalog'`).
- Profiles (`catalog/profiles.py`): **Catalog Manager** and **Admin** keep the
  catalogue. Other modules' profiles keep naming the catalogue codenames they
  need (`view_product`, `list_product`, ...).

## Models

| Model | Notes |
|---|---|
| `Product` | `nome`, `codigo` (unique per Entity), `unidade`, `preco_base`, `categoria`, `imagem`, `ativo`; `product_type` `goods` / `service` (a service never holds stock); `variant_of` + `variant_attributes` (one level: the product with variants is a template, stock/code/price live on the variants); `track_batches` and `estoque_minimo` are stock settings read only by inventory |
| `ProductCategory`, `ProductMedia` | categories and the product's photos/videos |
| `PriceList`, `PriceListItem` | price lists (`code` unique per Entity, validity, `active`) and quantity breaks (`min_quantity`, `price`) |

## Public services (`catalog/services.py`)

| Function | Returns |
|---|---|
| `catalog_module_active(entity_id)` | the module is active for the Entity |
| `get_product_snapshot(product_id, entity_id)` | `{id, codigo, nome, preco_base, track_batches, product_type, ativo}` of one of the Entity's products, or `None` |
| `get_price(product_id, entity_id, price_list_id, quantity, date)` | `{price, price_list}`: the list's price for the highest `min_quantity` ≤ quantity when the list is active and valid, else `preco_base` |
| `get_prices(product_ids, entity_id, price_list_id, date)` | the same for several products, in a fixed number of queries |
| `get_price_list_snapshot(price_list_id, entity_id)` | `{id, name}` or `None` |
| `is_stockable(product)` | goods without variants (a service or a template never holds stock) |

`inventory.services` keeps `get_product_snapshot`, `get_price`, `get_prices`,
`get_price_list_snapshot` and `holds_stock` as compatibility wrappers.

## Moved out of inventory (2026-11-11)

The catalogue lived in `inventory` (decision of 2026-10-11) and moved here so
that an Entity can sell catalogued services without stock (Catalog + Sales,
no Inventory). **No data was copied**: the models keep their tables
(`Meta.db_table` = `inventory_product`, `inventory_productcategory`,
`inventory_productmedia`, `inventory_pricelist`, `inventory_pricelistitem`)
and their ids.

- `catalog 0001_initial` (versioned): `SeparateDatabaseAndState` without
  database operations; moves the five ContentTypes to the `catalog` label (the
  permissions and the groups holding them are the same rows); activates the
  module for every Entity with inventory, sales, purchases or farmacia active.
- inventory's state migration (NOT versioned - inventory migrations are
  generated per installation): `SeparateDatabaseAndState` that removes the
  five models from inventory's state and points the foreign keys of stock
  items, movements, lots, reservations and count lines at `catalog.Product`
  (same table, no SQL). **In production it is written by hand** with the
  installation's last inventory migration as its dependency; a plain
  `makemigrations` would generate `DeleteModel` and drop the tables.
- Compatibility: `inventory.models` / `inventory.serializers` re-export the
  moved classes; `/api/inventory/{products, productcategorys, productmedias,
  pricelists, pricelistitems}/` stay (`inventory/views/catalog_compat.py`)
  while the inventory module is active. Remove both once nothing uses them.

Tests: `catalog/tests/` (catalog without inventory, tenant isolation, module
gate, services, the move); inventory's `test_catalogue.py` still covers
variants, price lists and the old routes.
