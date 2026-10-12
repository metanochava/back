"""Workflow: approvals by effective permission, steps and required
approvals, rejection, self-approval, registered actions (purchase order),
automatic start by event, inbox, tenant isolation."""
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase

from django_resaas.saas.core.tenant.context import ResaasContextService
from django_resaas.saas.models.branch_user import BranchUser
from django_resaas.saas.models.branch_user_group import BranchUserGroup
from django_resaas.saas.models.entity_user import EntityUser
from django_resaas.saas.models.group import Group
from django_resaas.saas.models.user import User
from rest_framework.test import APIClient
from testutils.tenant import bootstrap_tenant

from purchases import services as purchases
from purchases.models import PurchaseOrder
from purchases.tests.helpers import make_line, make_order, make_supplier
from workflow import services
from workflow.models import WorkflowDefinition, WorkflowInstance, WorkflowStep

WORKFLOW_PERMS = ("decide_workflowinstance", "cancel_workflowinstance", "inbox_workflowinstance",
                  "submit_purchaseorder", "approve_purchaseorder", "receive_purchaseorder")


def fields(tenant):
    return dict(entity=tenant["entity"], branch=tenant["branch"], created_by=tenant["user"], updated_by=tenant["user"])


def member(tenant, username, codenames):
    """Another user of the tenant, in a profile with exactly these permissions
    (plus reading workflow instances) - returns an authenticated client."""
    user = User.objects.create_user(username=username, email=f"{username}@example.com", password="x-pass-123")
    EntityUser.objects.create(entity=tenant["entity"], user=user)
    BranchUser.objects.create(branch=tenant["branch"], user=user)
    group = Group.objects.create(name=f"Profile {username}")
    group.permissions.set(Permission.objects.filter(codename__in=[
        *codenames, "view_workflowinstance", "list_workflowinstance", "inbox_workflowinstance",
        "decide_workflowinstance", "cancel_workflowinstance",
    ]))
    BranchUserGroup.objects.create(branch=tenant["branch"], user=user, group=group)
    issued = ResaasContextService.issue(
        user=user, entity_id=tenant["entity"].id, branch_id=tenant["branch"].id, group_id=group.id
    )
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_RESAAS_CONTEXT=issued["token"], HTTP_L="1")
    return user, client


class WorkflowTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("wf", modules=("workflow", "purchases"), extra_permissions=WORKFLOW_PERMS)
        self.client = self.tenant["client"]
        self.definition = WorkflowDefinition.objects.create(
            name="PO approval", code="PO", target_model="purchases.PurchaseOrder",
            on_approved_action="purchases.approve_order", **fields(self.tenant)
        )
        WorkflowStep.objects.create(
            definition=self.definition, order=1, name="Finance", approver_permission="approve_purchaseorder",
            required_approvals=2, **fields(self.tenant)
        )
        WorkflowStep.objects.create(
            definition=self.definition, order=2, name="Director", approver_permission="approve_purchaseorder",
            **fields(self.tenant)
        )
        self.order = make_order(self.tenant, make_supplier(self.tenant))
        make_line(self.tenant, self.order, quantity=Decimal("2"), unit_cost=Decimal("10"))
        purchases.submit_order(order=self.order, user=self.tenant["user"])

        self.ana, self.ana_client = member(self.tenant, "wf-ana", ["approve_purchaseorder"])
        self.rui, self.rui_client = member(self.tenant, "wf-rui", ["approve_purchaseorder"])
        self.eva, self.eva_client = member(self.tenant, "wf-eva", [])

    def _start(self):
        response = self.client.post("/api/workflow/instances/", {
            "definition": str(self.definition.id), "object_id": str(self.order.id),
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    def _decide(self, client, instance_id, decision="approve", comment=None):
        return client.post(f"/api/workflow/instances/{instance_id}/decide/", {
            "decision": decision, "comment": comment,
        }, format="json")

    def test_full_approval_runs_the_registered_action(self):
        instance_id = self._start()
        self.assertEqual(self.client.post(f"/api/purchases/purchaseorders/{self.order.id}/approve/").status_code, 409)

        self.assertEqual(self._decide(self.client, instance_id).status_code, 403)  # the starter
        self.assertEqual(self._decide(self.eva_client, instance_id).status_code, 403)  # no permission

        self.assertEqual(self._decide(self.ana_client, instance_id).status_code, 202)
        self.assertEqual(self._decide(self.ana_client, instance_id).status_code, 409)  # once per step
        instance = WorkflowInstance.objects.get(id=instance_id)
        self.assertEqual(instance.current_step.name, "Finance")  # needs 2 approvals

        self._decide(self.rui_client, instance_id)
        instance.refresh_from_db()
        self.assertEqual(instance.current_step.name, "Director")

        self.assertEqual(self._decide(self.ana_client, instance_id).status_code, 202)
        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowInstance.STATUS_APPROVED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, PurchaseOrder.STATUS_APPROVED)
        self.assertEqual(self.order.approved_by, self.ana)

    def test_rejection_needs_a_reason_and_returns_the_order_to_draft(self):
        instance_id = self._start()
        self.assertEqual(self._decide(self.ana_client, instance_id, "reject").status_code, 400)
        self.assertEqual(self._decide(self.ana_client, instance_id, "reject", "Too expensive").status_code, 202)

        instance = WorkflowInstance.objects.get(id=instance_id)
        self.assertEqual(instance.status, WorkflowInstance.STATUS_REJECTED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, PurchaseOrder.STATUS_DRAFT)
        self.assertEqual(self._decide(self.rui_client, instance_id).status_code, 409)

    def test_one_pending_instance_per_object_and_cancel(self):
        instance_id = self._start()
        response = self.client.post("/api/workflow/instances/", {
            "definition": str(self.definition.id), "object_id": str(self.order.id),
        }, format="json")
        self.assertEqual(response.status_code, 409)

        self.assertEqual(self.ana_client.post(f"/api/workflow/instances/{instance_id}/cancel/").status_code, 403)
        self.assertEqual(self.client.post(f"/api/workflow/instances/{instance_id}/cancel/").status_code, 202)
        self._start()

    def test_inbox_lists_what_the_user_can_decide(self):
        instance_id = self._start()
        ids = [row["id"] for row in self.ana_client.get("/api/workflow/instances/inbox/").data]
        self.assertEqual(ids, [instance_id])
        self.assertEqual(self.eva_client.get("/api/workflow/instances/inbox/").data, [])
        self.assertEqual(self.client.get("/api/workflow/instances/inbox/").data, [])  # starter

        self._decide(self.ana_client, instance_id)
        self.assertEqual(self.ana_client.get("/api/workflow/instances/inbox/").data, [])
        self.assertEqual(len(self.rui_client.get("/api/workflow/instances/inbox/").data), 1)

    def test_start_event_starts_an_instance_by_itself(self):
        self.definition.start_event = "purchases.order.submitted"
        self.definition.save()
        order = make_order(self.tenant, make_supplier(self.tenant))
        make_line(self.tenant, order)

        purchases.submit_order(order=order, user=self.tenant["user"])
        instance = WorkflowInstance.objects.get(object_id=str(order.id))
        self.assertEqual(instance.status, WorkflowInstance.STATUS_PENDING)
        self.assertEqual(instance.started_by, self.tenant["user"])

    def test_definition_validation(self):
        response = self.client.post("/api/workflow/definitions/", {
            "name": "Bad", "code": "BAD", "target_model": "purchases.PurchaseOrder",
            "on_approved_action": "os.system",
        }, format="json")
        self.assertEqual(response.status_code, 400)

        response = self.client.post("/api/workflow/steps/", {
            "definition": str(self.definition.id), "order": 3, "name": "X", "approver_permission": "no_such_perm",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_action_failure_undoes_the_decision(self):
        instance_id = self._start()
        WorkflowStep.objects.filter(definition=self.definition, order=2).delete()
        WorkflowStep.objects.filter(definition=self.definition, order=1).update(required_approvals=1)
        # the order left 'submitted' by other means: approve_order will refuse
        PurchaseOrder.objects.filter(id=self.order.id).update(status=PurchaseOrder.STATUS_DRAFT)

        self.assertEqual(self._decide(self.ana_client, instance_id).status_code, 409)
        instance = WorkflowInstance.objects.get(id=instance_id)
        self.assertEqual(instance.status, WorkflowInstance.STATUS_PENDING)
        self.assertFalse(instance.decisions.exists())


class WorkflowTenantTests(TestCase):

    def test_isolation(self):
        a = bootstrap_tenant("wf-a", modules=("workflow", "purchases"), extra_permissions=WORKFLOW_PERMS)
        b = bootstrap_tenant("wf-b", modules=("workflow", "purchases"), extra_permissions=WORKFLOW_PERMS)
        definition_a = WorkflowDefinition.objects.create(
            name="A", code="A", target_model="purchases.PurchaseOrder", **fields(a)
        )
        WorkflowStep.objects.create(definition=definition_a, name="S", approver_permission="approve_purchaseorder", **fields(a))
        definition_b = WorkflowDefinition.objects.create(
            name="B", code="B", target_model="purchases.PurchaseOrder", **fields(b)
        )
        WorkflowStep.objects.create(definition=definition_b, name="S", approver_permission="approve_purchaseorder", **fields(b))
        order_a = make_order(a, make_supplier(a))

        # another Entity's definition, or another Entity's object
        response = b["client"].post("/api/workflow/instances/", {
            "definition": str(definition_a.id), "object_id": str(order_a.id)}, format="json")
        self.assertEqual(response.status_code, 400)
        response = b["client"].post("/api/workflow/instances/", {
            "definition": str(definition_b.id), "object_id": str(order_a.id)}, format="json")
        self.assertEqual(response.status_code, 400)

        instance = services.start_instance(definition=definition_a, object_id=order_a.id, user=a["user"])
        self.assertEqual(b["client"].get(f"/api/workflow/instances/{instance.id}/").status_code, 404)
        self.assertEqual(b["client"].get("/api/workflow/instances/inbox/").data, [])

    def test_module_inactive(self):
        tenant = bootstrap_tenant("wf-off")
        self.assertEqual(tenant["client"].get("/api/workflow/instances/").status_code, 403)
