"""Reprint of a clinical document: the same document, only the date printed
next to the signature is the one asked (GET <document>/<id>/pdf/?date=YYYY-MM-DD).
Nothing is saved - the record keeps its own dates."""
from datetime import date

from django_resaas.saas.core.exceptions import ResaasAPIException


def print_date(request):
    """The `date` of the PDF request, or None (the document's own date)."""
    value = (request.query_params.get("date") or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ResaasAPIException("Choose a valid date.", code="invalid_date",
                                 details={"date": ["Choose a valid date."]})
