"""{{ entity.name|clinic_name }} -> "Clínica Amal": the Entity as the
clinic named in the header of the health PDFs. A name that already starts
with the word (Clínica/Clinica) is kept as it is."""
import unicodedata

from django import template

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
