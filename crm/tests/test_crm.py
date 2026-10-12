"""CRM: lead lifecycle and conversion, pipeline moves (won/lost), activities,
pipeline summary, references checked inside the Entity, permissions."""
from decimal import Decimal

from django.test import TestCase

from testutils.tenant import bootstrap_tenant

from crm import services
from crm.models import Activity, Lead, Opportunity, Stage

ACTIONS = (
    "mark_contacted_lead", "qualify_lead", "disqualify_lead", "reopen_lead", "convert_lead",
    "create_defaults_stage", "move_opportunity", "pipeline_opportunity", "complete_activity",
)


def fields(tenant):
    return dict(entity=tenant["entity"], branch=tenant["branch"], created_by=tenant["user"], updated_by=tenant["user"])


class CrmTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("crm", modules=("crm", "sales"), extra_permissions=ACTIONS)
        self.client = self.tenant["client"]
        response = self.client.post("/api/crm/stages/create_defaults/")
        self.assertEqual(response.status_code, 201, response.data)
        self.stages = {s.name: s for s in Stage.objects.filter(entity=self.tenant["entity"])}
        self.lead = Lead.objects.create(name="Ana", company_name="ACME", **fields(self.tenant))

    def _lead_action(self, action, **data):
        return self.client.post(f"/api/crm/leads/{self.lead.id}/{action}/", data, format="json")

    def test_default_stages_only_once(self):
        self.assertEqual(len(self.stages), 6)
        self.assertTrue(self.stages["Won"].is_won)
        self.assertEqual(self.client.post("/api/crm/stages/create_defaults/").status_code, 409)

    def test_lead_lifecycle(self):
        self.assertEqual(self._lead_action("mark_contacted").data["status"]["value"], "contacted")
        self.assertEqual(self._lead_action("disqualify").status_code, 400)  # reason required
        self.assertEqual(self._lead_action("disqualify", reason="No budget").data["status"]["value"], "disqualified")
        self.assertEqual(self._lead_action("convert").status_code, 409)
        self.assertEqual(self._lead_action("reopen").data["status"]["value"], "new")
        self.assertEqual(self._lead_action("qualify").data["status"]["value"], "qualified")
        self.assertEqual(self._lead_action("mark_contacted").status_code, 409)

        self.client.patch(f"/api/crm/leads/{self.lead.id}/", {"status": "converted"}, format="json")
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, "qualified")

    def test_convert_creates_an_open_opportunity_once(self):
        response = self._lead_action("convert", amount="5000", title="ERP deal")
        self.assertEqual(response.status_code, 202, response.data)
        opportunity = Opportunity.objects.get(id=response.data["id"])
        self.assertEqual(opportunity.stage, self.stages["Prospecting"])
        self.assertEqual(opportunity.amount, Decimal("5000"))
        self.assertEqual(opportunity.lead, self.lead)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, Lead.STATUS_CONVERTED)

        self.assertEqual(self._lead_action("convert").status_code, 409)
        self.assertEqual(Opportunity.objects.count(), 1)

    def test_convert_with_a_sales_customer_of_the_entity_only(self):
        from sales.tests.helpers import make_customer

        other = bootstrap_tenant("crm-other", modules=("crm", "sales"))
        foreign = make_customer(other)
        self.assertEqual(self._lead_action("convert", customer_id=str(foreign.id)).status_code, 400)

        own = make_customer(self.tenant)
        response = self._lead_action("convert", customer_id=str(own.id))
        self.assertEqual(response.status_code, 202, response.data)
        self.assertEqual(response.data["customer_name"], own.display_name)

    def test_move_won_lost_and_reopen(self):
        opportunity = services.convert_lead(lead=self.lead, user=self.tenant["user"], amount=100)
        base = f"/api/crm/opportunities/{opportunity.id}/move/"

        response = self.client.post(base, {"stage": str(self.stages["Lost"].id)}, format="json")
        self.assertEqual(response.status_code, 400)  # reason required

        response = self.client.post(base, {"stage": str(self.stages["Lost"].id), "lost_reason": "Price"}, format="json")
        self.assertEqual(response.data["status"]["value"], "lost")
        self.assertIsNotNone(response.data["closed_at"])

        response = self.client.post(base, {"stage": str(self.stages["Proposal"].id)}, format="json")
        self.assertEqual(response.data["status"]["value"], "open")
        self.assertIsNone(response.data["closed_at"])

        response = self.client.post(base, {"stage": str(self.stages["Won"].id)}, format="json")
        self.assertEqual(response.data["status"]["value"], "won")

    def test_stage_and_status_are_not_changed_by_crud(self):
        opportunity = services.convert_lead(lead=self.lead, user=self.tenant["user"])
        self.client.patch(f"/api/crm/opportunities/{opportunity.id}/", {
            "stage": str(self.stages["Won"].id), "status": "won", "title": "Renamed",
        }, format="json")
        opportunity.refresh_from_db()
        self.assertEqual(opportunity.stage, self.stages["Prospecting"])
        self.assertEqual(opportunity.status, "open")
        self.assertEqual(opportunity.title, "Renamed")

        response = self.client.post("/api/crm/opportunities/", {
            "title": "Direct", "stage": str(self.stages["Won"].id),
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_pipeline_summary(self):
        a = services.convert_lead(lead=self.lead, user=self.tenant["user"], amount=1000)
        lead_b = Lead.objects.create(name="Bruno", **fields(self.tenant))
        b = services.convert_lead(lead=lead_b, user=self.tenant["user"], amount=400, stage=self.stages["Proposal"])
        lead_c = Lead.objects.create(name="Carla", **fields(self.tenant))
        c = services.convert_lead(lead=lead_c, user=self.tenant["user"], amount=999)
        services.move_opportunity(opportunity=c, user=self.tenant["user"], stage=self.stages["Won"])

        data = self.client.get("/api/crm/opportunities/pipeline/").data
        rows = {row["name"]: row for row in data["stages"]}
        self.assertEqual(rows["Prospecting"]["count"], 1)
        self.assertEqual(Decimal(str(rows["Prospecting"]["weighted_amount"])), Decimal("100.00"))
        self.assertEqual(Decimal(str(rows["Proposal"]["amount"])), Decimal("400"))
        self.assertNotIn("Won", rows)
        self.assertEqual(Decimal(str(data["total_amount"])), Decimal("1400"))
        self.assertEqual(Decimal(str(data["total_weighted_amount"])), Decimal("300.00"))

    def test_activities(self):
        response = self.client.post("/api/crm/activities/", {"subject": "Call", "activity_type": "call"}, format="json")
        self.assertEqual(response.status_code, 400)

        response = self.client.post("/api/crm/activities/", {
            "subject": "Call", "activity_type": "call", "lead": str(self.lead.id),
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        activity_id = response.data["id"]

        response = self.client.post(f"/api/crm/activities/{activity_id}/complete/")
        self.assertTrue(response.data["done"])
        self.assertEqual(self.client.post(f"/api/crm/activities/{activity_id}/complete/").status_code, 409)

    def test_owner_must_be_a_user_of_the_entity(self):
        other = bootstrap_tenant("crm-owner", modules=("crm",))
        response = self.client.patch(f"/api/crm/leads/{self.lead.id}/", {"owner": other["user"].id}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(f"/api/crm/leads/{self.lead.id}/", {"owner": self.tenant["user"].id}, format="json")
        self.assertEqual(response.status_code, 200, response.data)


class CrmTenantTests(TestCase):

    def setUp(self):
        self.a = bootstrap_tenant("crm-a", modules=("crm",), extra_permissions=ACTIONS)
        self.b = bootstrap_tenant("crm-b", modules=("crm",), extra_permissions=ACTIONS)
        self.a["client"].post("/api/crm/stages/create_defaults/")
        self.b["client"].post("/api/crm/stages/create_defaults/")
        self.lead_a = Lead.objects.create(name="A", **fields(self.a))
        self.opportunity_a = services.convert_lead(lead=self.lead_a, user=self.a["user"])

    def test_isolation(self):
        client = self.b["client"]
        self.assertEqual(client.get("/api/crm/leads/").data["count"], 0)
        self.assertEqual(client.get(f"/api/crm/opportunities/{self.opportunity_a.id}/").status_code, 404)
        self.assertEqual(client.post(f"/api/crm/leads/{self.lead_a.id}/qualify/").status_code, 404)
        self.assertEqual(client.get("/api/crm/opportunities/pipeline/").data["total_amount"], 0)

    def test_another_entitys_stage_cannot_be_used(self):
        stage_b = Stage.objects.filter(entity=self.b["entity"]).first()
        response = self.a["client"].post(
            f"/api/crm/opportunities/{self.opportunity_a.id}/move/", {"stage": str(stage_b.id)}, format="json"
        )
        self.assertEqual(response.status_code, 400)

        response = self.b["client"].post("/api/crm/activities/", {
            "subject": "x", "lead": str(self.lead_a.id),
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_module_inactive(self):
        tenant = bootstrap_tenant("crm-off")
        self.assertEqual(tenant["client"].get("/api/crm/leads/").status_code, 403)

    def test_crm_without_sales_rejects_a_customer(self):
        from unittest import mock

        lead = Lead.objects.create(name="Z", **fields(self.a))
        with mock.patch("crm.services.apps.is_installed", return_value=False):
            with self.assertRaises(Exception):
                services.convert_lead(lead=lead, user=self.a["user"], customer_id="00000000-0000-0000-0000-000000000001")
        self.assertEqual(Activity.objects.count(), 0)
