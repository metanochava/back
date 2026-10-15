from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class _AddressThrottle(SimpleRateThrottle):
    """Per client address, signed in or not (a public form is abused by address)."""

    setting = None
    default_rate = None

    def get_rate(self):
        return getattr(settings, self.setting, self.default_rate)

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
