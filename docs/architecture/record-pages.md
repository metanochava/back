# Record pages (`view_<model>`)

A list row's "view" opens the schema's `routes.view`, which is `view_<model>`.
Models without a page of their own get a record page with the layout of the
employee's profile (2026-11-12):

- a header with the record, its status, Pdf, Edit and Reload;
- tabs:
  - **Details:** the record's own fields, read-only;
  - **related records:** the records of models that point at it;
  - **person:** the record's Person, in the same `PersonProfilePanel` as the
    employee's;
  - **action:** the rows of a GET action of the record, such as `history`.

Every part is front-end only, in dev/front. The package (quasar_resaas) and
Health (`saude`) are not touched. On the backend, the related tabs use the
generic `?<field>=<id>` filter of BaseAPIView.

| Part | Where (dev/front) |
|---|---|
| Page | `src/components/record/RecordViewPage.vue` |
| Related records tab | `RelatedTable.vue`: the related model's schema table, the parent column hidden, a new record already attached |
| Action tab | `ActionRows.vue` |
| Routes | `viewRoutes(app, views)` in `viewRoutes.js` |
| Field permissions | `fieldAccess.js`: the same rules as the package's, which does not export them |
| Per module | `src/pages/<module>/views.js` (`<app>Views`), spread in its `routes.js` |
| Spec | `views.spec.js`: every module's configuration and routes |

## Form pages (`add_<model>`, `change_<model>/:id`, 2026-11-19)

Every model with a list and no form page of its own gets
`add_<model>` and `change_<model>/:id`, rendered by
`src/components/record/RecordFormPage.vue`: the schema's form (`s-form`) over a
store whose `safeUrl` is the model's endpoint, Save / Cancel, then the record's
`view_` page (or the list).

- `formRoutes(app, views | modelNames)` builds them; `missingFormRoutes(routes,
  sources)` keeps only the names no module already has - a module's own page
  always wins. `src/router/routes.js` (`FORM_SOURCES`) lists every module's
  `views.js` plus the models of modules without one.
- A view with `form: false` keeps its own pages.
- The page honours `schema.operations` (django_resaas): a read-only endpoint
  (StockItem) shows "These records cannot be created here."; a profile without
  `add_/change_<model>` sees "Your profile cannot do this." The backend checks
  everything again.
- **Not generated on purpose:** Health (`saude`); the workflow pages with their
  own actions (`sale`, `dispensa`, `inventorycount`, `journalentry`,
  `purchaseorder`); the notifications' system records; `formdefinition` and
  `app`.
- Tests: `formRoutes.spec.js`, `RecordFormPage.spec.js`.

## A module's `views.js`

```js
export const salesViews = {
  Customer: {
    label: 'Customer', icon: 'groups',
    title: (r) => label(r.company_name),
    statusField: null,
    defaultTab: 'personal',
    tabs: [
      { name: 'personal', label: 'Personal', icon: 'person', person: 'person', permission: 'view_person' },
      { name: 'sale', label: 'Sales', icon: 'point_of_sale', model: 'Sale', fk: 'customer' }
    ]
  }
}
```

**Header**

- `title` and `subtitle` read the row. Without them, the title is the row's
  `label`.
- `statusField` names the status field (`status` by default, `null` for
  none).

**Tabs**

- A related tab (`model` + `fk`) shows only with `list_<model>`.
- Any tab may instead name its own `permission`.
- `app` is needed when the related model belongs to another app.

## Rules

- **A model with a custom `view_` page keeps it.** Its model is not listed in
  `views.js` (the spec checks that every route name is unique).
  - In HR, for example, `view_employee` and 44 more stay as they are.
  - In the other modules: `view_sale`, `view_purchaseorder`,
    `view_journalentry`, `view_opportunity`, `view_workflowinstance`,
    `view_dispensa`, `view_inventorycount`.
- **Health (`saude`) has no record pages here.**
- **A model with no API view has no page.** For example,
  EnrolmentStatusChange and GradeRevision are read through their parent's
  `history` action instead.
- **Labels are canonical English** with pt-pt in the owning app's
  `lang/ptpt.py`.

## Modules

| Module (front folder) | Models |
|---|---|
| academica (the former ensino, `src/pages/academica`) | 18 (tabs written by hand) |
| stock (catalog, inventory) | 13 |
| vendas (sales) | 5 |
| purchases | 4 |
| accounting | 5 |
| crm | 3 |
| workflow | 2 |
| farmacia | 7 |
| hr | 13 (only the models without a custom page) |

The configurations outside academica were generated from the models: an API view,
no `view_` route, and the related models among the exposed ones. Reviewed
titles and labels may be refined by hand.
