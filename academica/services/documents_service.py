"""The academic documents (PDF, django_resaas PDF()): an enrolment's report
card, a class's grade sheet (pauta) and a student's transcript (every year
here, plus the schooling declared from other institutions). The school's
colour and logo come from django_resaas qr_card_service; every text is
translated with the request language."""
from django_resaas.saas.core.services import qr_card_service
from django_resaas.saas.core.utils.bar_qr_code_64 import png_bytes_to_b64
from django_resaas.saas.core.utils.translate import Translate

from academica.models import Enrolment
from academica.services import grading_service


def _brand(request, entity):
    logo = qr_card_service._read(entity.logo)
    return {"entity": entity, "color": qr_card_service.brand_color(entity),
            "logo_b64": png_bytes_to_b64(logo) if logo else None,
            "t": lambda text: Translate.tdc(request, text)}


def _labels(request, *keys):
    return {key.replace(" ", "_").lower(): Translate.tdc(request, key) for key in keys}


COMMON = ("Student", "Number", "Class", "Grade level", "Academic year", "Subject", "Average", "Result",
          "Passed", "Not passed", "No grades", "Issued on", "Report card", "Grade sheet", "Transcript",
          "Programme", "Status", "Institution", "Prior schooling", "Period")


def report_card(request, enrolment, period=None):
    rows = grading_service.report(enrolment, period.id if period else None)
    return {**_brand(request, enrolment.entity), "labels": _labels(request, *COMMON), "enrolment": enrolment,
            "period": period, "rows": rows, "pdf_subject": "Report card",
            "pdf_person": enrolment.student.person.full_name}


def class_sheet(request, class_group, academic_year=None, period=None):
    enrolments = (Enrolment.objects.filter(class_group=class_group, status__in=Enrolment.HOLDING + (Enrolment.STATUS_COMPLETED,))
                  .select_related("student__person").order_by("student__person__full_name"))
    if academic_year:
        enrolments = enrolments.filter(academic_year=academic_year)
    reports = {e.id: {row["subject"]: row for row in grading_service.report(e, period.id if period else None)}
               for e in enrolments}
    subjects = sorted({name for report in reports.values() for name in report})
    lines = [{"enrolment": e, "cells": [reports[e.id].get(name) for name in subjects]} for e in enrolments]
    return {**_brand(request, class_group.entity), "labels": _labels(request, *COMMON), "class_group": class_group,
            "period": period, "subjects": subjects, "lines": lines, "pdf_subject": "Grade sheet",
            "pdf_person": class_group.name}


def transcript(request, student):
    years = []
    for e in (student.enrolments.select_related("academic_year", "grade_level", "programme")
              .order_by("academic_year__start_date")):
        years.append({"enrolment": e, "rows": grading_service.report(e)})
    return {**_brand(request, student.entity), "labels": _labels(request, *COMMON), "student": student,
            "years": years, "prior": list(student.prior_schooling.order_by("academic_year")),
            "pdf_subject": "Transcript", "pdf_person": student.person.full_name}
