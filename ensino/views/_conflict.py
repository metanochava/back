from django.db import IntegrityError, transaction

from django_resaas.saas.core.exceptions import ResaasAPIException


class UniqueConflictMixin:
    """A record that already exists (a database unique constraint) answers 409,
    never a 500 - the serializers have no automatic unique validators."""

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                super().perform_create(serializer)
        except IntegrityError:
            raise ResaasAPIException("This record already exists.", code="already_exists", status_code=409)

    def perform_update(self, serializer):
        try:
            with transaction.atomic():
                super().perform_update(serializer)
        except IntegrityError:
            raise ResaasAPIException("This record already exists.", code="already_exists", status_code=409)
