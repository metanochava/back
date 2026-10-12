from purchases.profiles import ACTION_PERMISSIONS, PURCHASES_PROFILES
from purchases.views.purchase_order import PurchaseOrderAPIView


def test_action_permissions_match_the_declared_actions():
    declared = {
        f"{metadata['action']}_purchaseorder"
        for metadata in (
            getattr(getattr(PurchaseOrderAPIView, name), "_resaas_action", None) for name in dir(PurchaseOrderAPIView)
        )
        if metadata and metadata["action"] not in ("restore", "hard_delete", "pdf", "pdf_list", "schema")
    }
    assert set(ACTION_PERMISSIONS) == declared & set(ACTION_PERMISSIONS)
    assert {"submit", "return_to_draft", "approve", "cancel", "receive"} <= {c.rsplit("_purchaseorder", 1)[0] for c in declared}


def test_receiving_is_separate_from_buying():
    profiles = {profile["name"]: set(profile["permissions"]) for profile in PURCHASES_PROFILES}
    assert "approve_purchaseorder" not in profiles["Buyer"]
    assert "receive_purchaseorder" not in profiles["Buyer"]
    assert "receive_purchaseorder" in profiles["Receiving Clerk"]
    assert "approve_purchaseorder" not in profiles["Receiving Clerk"]
