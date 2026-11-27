# Navigation menus — current architecture and migration plan

Status: discovery (phase 1 and 2 of the dynamic menus work). No behaviour change yet.
Measured 2026-11-27 on `django_resaas` `fix/tenant-read-roles` (b0897e31) and `back` `develop` (65ed5e2).

## How the sidebar is built today

`django_resaas/saas/core/menus.py::build_menus(request)` is the single entry point. It is
called by `UserAPIView.menus` (`users/{id}/menus/`) and by `core/services/boot_service.py`
(boot payload `answer["menus"]`).

1. Returns `[]` when the request has no `entity_type_id`.
2. `menu_permissions(request)`: the `BranchUserGroup` of the request's user, branch and group
   (state Active). Returns the group's permission codenames minus `hidden_menu_permissions`,
   plus `hidden_menu_apps`. No superuser bypass, by design.
3. `active_app_names(entity_type_id)`: apps linked to the EntityType through `EntityTypeApp`.
4. Apps are ordered: platform (`django_resaas*` or dotted names) first, then `settings.MY_APPS`.
5. For each app: skipped unless active (`is_active_app`) **and** `has_module(request, label)`
   (entitlements, `core/entitlements/service.py`).
6. Imports `<app>.sidebar` and reads `ALL`. Each item:
   - Direct link (`MENU`, `ROUTE`, no `SUBMENUS`): shown only when its `ROLE` is in the
     permissions. No `ROLE` means hidden (fail closed).
   - Menu with `SUBMENUS`: skipped when the app is in `hidden_menu_apps`; otherwise
     `filter_menu_by_permission(SUBMENUS, perms)`, which is recursive and keeps a node when it
     has an authorised `role` or a visible descendant. `role` and `add_role` are removed from the
     payload; `add_route` is removed when `add_role` is not authorised.

Payload shape (the frontend contract, do not change without a compatibility path):
`menu`, `icon`, `app`, `app_label`, plus `route` (direct link) or `submenu` (list of nodes,
each with `menu`, `icon`, `route`, `add_route`, `submenu`).

## Where menus are declared

- `<app>/sidebar.py` in each `back` app: `saude`, `hr`, `sales`, `inventory`, `purchases`,
  `accounting`, `crm`, `catalog`, `workflow`, `academica`, `farmacia`, `hospitality`,
  `laboratorio`, `pedagogica` (14 files; most declare one top-level menu).
- `django_resaas/src/django_resaas/saas/sidebar.py` and
  `django_resaas/src/django_resaas/notifications/sidebar.py` (platform menus).

## Consumers of the sidebar declarations

- `build_menus` (payload above).
- `core/menus.py::menu_roles()`: reads every `<app>.sidebar` `ROLE` and submenu `role`/`add_role`
  to build the set of roles the Permissions modal may toggle (`Group.hidden_menu_permissions`).
  **This consumer must be replaced before `sidebar.py` is removed**, or the modal loses the
  menu-visibility toggles.

Frontend (`quasar_resaas`): `components/SubMenu.vue` is recursive (it renders itself for
`item.submenu`); `LeftMenuSegundo.vue`, `TopMenuSegundo.vue`, `SearchMenu.vue` and
`services/routing.js` consume the payload.

## Permissions and modules

- Menu permissions follow the profile (BranchUserGroup) like API permissions, but a menu
  never grants access: the API keeps validating each endpoint.
- Module activation: `EntityTypeApp` (module active for the entity type) and `has_module`
  (entitlement). No new activation table is needed.
- Route names are referenced by string; nothing checks that a route is registered
  (`register_view` / `VIEW_REGISTRY` in `core/base/views.py`).
- `class RESAAS` metadata is present on 155 `back` models (`crud`, `search_fields`, `routes`,
  `permissions`, `label`). This is the candidate source for resource discovery.

## Migration plan (not started)

1. Keep `build_menus(request)` and its payload. A new implementation reads database
   configuration first and falls back to `sidebar.py` per app while migrating.
2. Replace `menu_roles()` first: derive the toggle list from the database menu items (or from the
   current sidebars during the transition), so the Permissions modal keeps working.
3. Migrate sidebars one app at a time with an idempotent command; compare old and new payloads per
   profile before removing each `sidebar.py`.
4. Remove `sidebar.py` only after the comparison is equal for every profile and every EntityType.

## Divergences found

- `django_resaas` has no `docs/architecture/` folder, although `CLAUDE.md` refers to
  `docs/architecture/dashboards.md` there. This document lives in `back` because that is where the
  existing architecture docs are.

## Status (2026-11-27)

- Database menus exist (`django_resaas` migration `0027_menus`): `Menu`, `MenuItem`, `MenuModule`, `MenuItemModule`.
- `build_menus` uses the database tree for each app that an active menu is presented in (`MenuModule`). Other apps and all direct top-level links still come from `sidebar.py`.
- `manage.py migrate_sidebars` copies the sidebar submenus into the database (dry run by default, `--apply` to write). Applied on dev only.
- On dev, the migrated trees equal the sidebar trees for all 24 profiles (checked with rollback).
- Not done: Menu Manager API, cache, removal of `sidebar.py` (blocked by `menu_roles()` and approval).
- Menu Manager API (phase 13): `/api/django_resaas/menus/` (CRUD, plus `validate/` and `resources/`) and `/api/django_resaas/menuitems/` (CRUD, `?menu=` filter). Platform administration: permissions `list/view/add/change/delete_menu` and `..._menuitem`, held by the Root group only. Framework menus (`is_system`) cannot be deleted.
