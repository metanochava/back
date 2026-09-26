"""Who may edit a clinical document, and until when.

A consultation, prescription (and its items), certificate, referral, report
or exam request is edited only by the user who created it, and only within
EDIT_WINDOW of its creation (24 h; settings.SAUDE_DOCUMENT_EDIT_WINDOW_HOURS).
After that the document stands as issued. Enforced on every update (PUT/PATCH,
including a reprint that changes the dates) by DocumentEditWindowMixin; the
frontend only hides the buttons.
"""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import status

from django_resaas.saas.core.exceptions import ConflictError, ResaasAPIException


def edit_window():
    return timedelta(hours=getattr(settings, "SAUDE_DOCUMENT_EDIT_WINDOW_HOURS", 24))


def check_editable(request, document, now=None):
    if document.created_by_id != getattr(request.user, "id", None):
        raise ResaasAPIException(
            "Only the person who created this document can edit it.",
            code="not_document_author",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if (now or timezone.now()) - document.created_at > edit_window():
        raise ConflictError(
            "This document can no longer be edited: it can only be changed within 24 hours of its creation.",
            code="edit_window_expired",
        )


class DocumentEditWindowMixin:
    """For the BaseAPIView of a clinical document: the permission to change it
    is not enough - it must be the author's, within the edit window."""

    def perform_update(self, serializer):
        check_editable(self.request, serializer.instance)
        super().perform_update(serializer)
