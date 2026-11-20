"""No hospitality endpoint is PUBLIC by omission (the guard of django_resaas'
tests/test_rest_architecture.py, for this module): every view is a BaseAPIView
(protected by initial()), except the views listed here on purpose - the page
a table's QR code opens, which finds the table only from its secret token."""
import importlib
import inspect
import pkgutil

from django.test import SimpleTestCase
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from django_resaas.saas.core.base.views import BaseAPIView

import hospitality.views

PUBLIC_BY_DESIGN = {"TableQrViewSet"}


def _views():
    for module in pkgutil.iter_modules(hospitality.views.__path__):
        loaded = importlib.import_module(f"hospitality.views.{module.name}")
        for _, cls in inspect.getmembers(loaded, inspect.isclass):
            if cls.__module__ == loaded.__name__ and issubclass(cls, APIView):
                yield cls


class AccessGuardTests(SimpleTestCase):

    def test_every_view_is_protected_or_public_by_name(self):
        views = list(_views())
        self.assertTrue(views)
        for view in views:
            with self.subTest(view=view.__name__):
                public = AllowAny in tuple(getattr(view, "permission_classes", ()))
                if view.__name__ in PUBLIC_BY_DESIGN:
                    self.assertTrue(public)
                    self.assertTrue(getattr(view, "throttle_classes", None) or hasattr(view, "get_throttles"))
                else:
                    self.assertTrue(issubclass(view, BaseAPIView), f"{view.__name__} must be a BaseAPIView")
