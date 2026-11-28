"""Module layering guard (docs/architecture/ecosystem.md, "Module layers").

Each business app may import only the apps listed for it below. The list is the
dependency matrix measured on the codebase: the horizontal modules never import
the vertical ones (saude), and no import cycle exists. Adding an import that
is not listed here is a layering change and must be reviewed first.

Only module-level and in-function imports of the app's own non-test, non-migration
Python files are read. Imports of third-party or framework packages are ignored.
"""
import re
from pathlib import Path

from django.test import SimpleTestCase

BACK_ROOT = Path(__file__).resolve().parents[2]

ALLOWED_IMPORTS = {
    "catalog": set(),
    "workflow": set(),
    "hr": set(),
    "accounting": set(),
    "inventory": {"catalog"},
    "sales": {"catalog", "inventory"},
    "purchases": {"inventory", "workflow"},
    "crm": {"sales"},
    "saude": {"catalog", "inventory", "sales", "hr"},
}

IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)


def _app_imports(app):
    found = set()
    for path in (BACK_ROOT / app).rglob("*.py"):
        parts = path.relative_to(BACK_ROOT).parts
        if "tests" in parts or "migrations" in parts or "__pycache__" in parts:
            continue
        found.update(IMPORT_RE.findall(path.read_text(encoding="utf-8", errors="ignore")))
    return {name for name in found if name in ALLOWED_IMPORTS and name != app}


class ModuleBoundariesTests(SimpleTestCase):

    def test_every_app_imports_only_its_declared_dependencies(self):
        for app, allowed in ALLOWED_IMPORTS.items():
            with self.subTest(app=app):
                self.assertLessEqual(_app_imports(app), allowed)

    def test_horizontal_modules_never_import_saude(self):
        for app in ("catalog", "inventory", "sales", "purchases", "crm", "accounting", "workflow", "hr"):
            with self.subTest(app=app):
                self.assertNotIn("saude", _app_imports(app))

    def test_dependency_graph_has_no_cycle(self):
        def reaches(start, target, seen):
            for dep in ALLOWED_IMPORTS.get(start, ()):
                if dep == target:
                    return True
                if dep not in seen:
                    seen.add(dep)
                    if reaches(dep, target, seen):
                        return True
            return False

        for app in ALLOWED_IMPORTS:
            with self.subTest(app=app):
                self.assertFalse(reaches(app, app, set()))
