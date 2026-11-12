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

## Not done yet

- Procedures (`Procedimento` has a free-text name, no catalogue): not charged.
- Undoing a check-out does not cancel the draft sale (cancel it in sales).
- Consolidating an admission's costs into one sale.
