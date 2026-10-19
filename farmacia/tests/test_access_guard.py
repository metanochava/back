"""No farmacia endpoint is PUBLIC by omission (the guard of django_resaas'
tests/test_rest_architecture.py, for this module): every view is a BaseAPIView
(protected by initial()) or an ExplicitAccessMixin view, and the only public
actions are the ones listed here on purpose."""
import importlib
import inspect
import pkgutil

from django.test import SimpleTestCase
from rest_framework.views import APIView

from django_resaas.saas.core.base.access import ExplicitAccessMixin
from django_resaas.saas.core.base.views import BaseAPIView

import farmacia.views

# view -> actions that answer anonymous GETs (pre-session: nearby pharmacies)
PUBLIC_BY_DESIGN = {"MarketplaceViewSet": ("pharmacies",)}


def _views():
    for module in pkgutil.iter_modules(farmacia.views.__path__):
        loaded = importlib.import_module(f"farmacia.views.{module.name}")
        for _, cls in inspect.getmembers(loaded, inspect.isclass):
            if cls.__module__ == loaded.__name__ and issubclass(cls, APIView):
                yield cls


class AccessGuardTests(SimpleTestCase):

    def test_every_view_is_protected_or_public_by_name(self):
        views = list(_views())
        self.assertTrue(views)
        for view in views:
            with self.subTest(view=view.__name__):
                self.assertTrue(issubclass(view, (BaseAPIView, ExplicitAccessMixin)),
                                f"{view.__name__} must be a BaseAPIView or use ExplicitAccessMixin")
                public = tuple(getattr(view, "public_actions", ()))
                self.assertEqual(public, PUBLIC_BY_DESIGN.get(view.__name__, ()))
