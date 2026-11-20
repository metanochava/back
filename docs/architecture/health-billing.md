# Health billing and material consumption

How clinical acts reach the commercial and stock modules (2026-11-12). Health
decides **when** (its clinical flow) and **what** (its rules); `catalog` says
what an item is and costs, `sales` makes the sale, `inventory` moves the
stock - each through its public services, never its models. No clinical model
moved: the links are mappings and per-act records in `saude`.

Code: `saude/models/clinical_billing.py`, `saude/services/clinical_billing_service.py`,
`saude/views/clinical_billing.py`, `saude/serializers/clinical_billing.py`;
frontend `front/src/pages/saude/billing/ClinicalBillingPage.vue` (menu
Saude → Billing). Tests: `saude/tests/test_clinical_billing.py`,
`saude/tests/test_integration_clinic.py`.

## Rules

| Model | Meaning |
|---|---|
| `ClinicalBillingRule` | a clinical service → a catalogued item and quantity: `consultation` (of a `specialty`, or empty = any consultation without its own rule), `exam` (an `ExameMedico`), `medication` (a `Medicamento` → its commercial presentations, several rules = several) |
| `ExamMaterialRule` | an exam → a catalogued good it uses up, with the quantity |

`product_id` is a loose id, checked to be one of the Entity's catalogued items
(`400` otherwise); the fields each kind uses are checked (an exam rule needs
its exam, a consultation rule takes no exam or medicine).

## When

| Clinical step | What happens | Record |
|---|---|---|
| Consultation checked out (`agendas/{id}/check_out/`) | the specialty's rules, else the general consultation rules, become a **draft sale** for the patient (`sales.customer_for_person` + `create_sale`) | `ClinicalCharge` (source `saude.agenda`) |
| Exam request checked in (`pedidoexamemedicos/{id}/check_in/`) | the rules of every exam requested (not cancelled) become a draft sale | `ClinicalCharge` (source `saude.pedidoexamemedico`) |
| Exam performed (`start_processing`, or the result recorded when there is no processing step) | its materials leave the branch's stock (`inventory.commit_consumption_movements`) | `MaterialConsumption` (source `saude.itempedidoexamemedico`) |

The check-out and the exam check-in answer the charge they made
(`charge: {sale_id}`; the exam check-in inside `data`), and the patient's page
says "Consultation charged" with a way to the sale. The sale is confirmed and
paid in `sales`, as any other.

## Rules of the flow

- Each act is charged once and consumed once (unique per act; repeating the
  step does nothing; a concurrent repeat is caught by the constraint).
- No rules, or `sales` / `catalog` not active (charges), or `inventory` not
  active (consumption): nothing happens - operations without charge.
- A prescription never moves stock; dispensing is pharmacy's own operation
  (`farmacia`, `commit_dispensation_movements`). The medicine's presentations
  are offered to it by `medication_presentations()`.
- Requesting an exam consumes nothing; only performing it does.
- Missing stock never blocks the clinical act: the consumption is recorded
  `failed` with the reason and tried again the next time the step runs. A
  billing error is logged and the step goes on.

## Permissions

Health Administrator keeps the rules and reads charges and consumptions;
Receptionist reads the charges (and confirms / receives sales with its sales
permissions).

## Prices on the public site

The clinic's site (`front/src/sites/amal`) shows the same prices the clinic
charges, read from these rules. The endpoints are PUBLIC and read-only, and
the Entity comes from the request Origin. They live in
`saude/views/public_site.py` and `saude/services/public_site_service.py`:

| Endpoint | Answers |
|---|---|
| `GET saude/publicsite/exams/` | every active exam (type, class, sample, result time) with its price, or `null` ("Price on request") |
| `GET saude/publicsite/exams/<id>/` | one exam: preparation, what the price includes (only with more than one item) and the items' images |
| `GET saude/publicsite/consultations/` | the price per specialty, and of the general consultation (key `general`) |
| `GET saude/publicsite/consultations/<key>/` | one consultation: price, what it includes, images and the specialty's doctors (all of them for the general one) |

**How a price is computed**

- It is the sum of quantity × the item's current catalog price, over the
  active rules (`catalog.get_prices`).
- The images come from `catalog.get_product_media`.
- An inactive item does not count.
- Without the catalog, there are no prices.

**What never reaches the site:** rules, item ids, costs or patient data.
Another clinic's exam, an inactive exam or an unknown key answers 404.

**On the site**

- the Exams section (search, filter by type);
- the Consultation prices section (`#precos`).

A card opens its details in a modal (`OfferDetailDialog.vue`, an
`s-modal-card` in a `q-dialog`). From a consultation's modal, "Book
appointment" opens the booking form with the specialty already chosen.

Tests: `saude/tests/test_public_site_prices.py` and
`front/src/sites/amal/pages/OfferPages.spec.js`.

## Not done yet

- Procedures (`Procedimento` has a free-text name, no catalogue): not charged.
- Undoing a check-out does not cancel the draft sale (cancel it in sales).
- Consolidating an admission's costs into one sale.
