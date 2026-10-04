"""Every saude feature reaches at least one profile (standing rule: a new
feature also grants its permissions to the profiles that use it).

- every permission a saude dashboard / widget / action or a resaas_action of
  a saude view requires is held by at least one saude profile - otherwise
  only Root could use it.
Frontend route requiredRole / User.can live in the front repository and are
audited there."""
import ast
import pathlib

from django.test import TestCase

from saude.dashboard import DASHBOARDS
from saude.profiles import SAUDE_PROFILES

SAUDE_DIR = pathlib.Path(__file__).resolve().parent.parent


def _dashboard_permissions():
    found = set()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("permissions",) and isinstance(value, list):
                    found.update(v for v in value if isinstance(v, str))
                elif key == "permission" and isinstance(value, str):
                    found.add(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(DASHBOARDS)
    return found


def _action_permissions():
    found = set()
    for path in (SAUDE_DIR / "views").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "resaas_action":
                for keyword in node.keywords:
                    if keyword.arg == "permission" and isinstance(keyword.value, ast.Constant):
                        found.add(keyword.value.value)
    return found


class ProfilesCoverFeaturesTests(TestCase):

    def test_every_dashboard_and_action_permission_reaches_a_profile(self):
        held = {code for profile in SAUDE_PROFILES for code in profile["permissions"]}
        required = _dashboard_permissions() | _action_permissions()

        self.assertTrue(required)
        self.assertEqual(sorted(required - held), [], "required by a saude feature but granted to no saude profile")
