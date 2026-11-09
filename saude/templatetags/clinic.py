"""{{ entity.name|clinic_name }} -> "Clínica Amal": the Entity as the
clinic named in the header of the health PDFs. A name that already starts
with the word (Clínica/Clinica) is kept as it is.

{{ value|long_date }} -> "08 de Novembro de 2026" and
{{ value|long_date:"time" }} -> "08 de Novembro de 2026 às 14:30": every
date printed on a health PDF is written out (medical_certificate_service.
long_date_pt). An aware datetime is shown in the local time zone."""
import datetime
import unicodedata

from django import template
from django.utils import timezone

register = template.Library()

PREFIX = "Clínica"


def _plain(value):
    return "".join(c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn").lower()


@register.filter
def clinic_name(name):
    name = (name or "").strip()
    if not name:
        return ""
    if _plain(name).startswith("clinica"):
        return name
    return f"{PREFIX} {name}"


@register.filter
def long_date(value, arg=""):
    from saude.services.medical_certificate_service import long_date_pt

    if not value or not isinstance(value, (datetime.date, datetime.datetime)):
        return value or ""
    if isinstance(value, datetime.datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        text = long_date_pt(value.date())
        return f"{text} às {value:%H:%M}" if arg == "time" else text
    return long_date_pt(value)
