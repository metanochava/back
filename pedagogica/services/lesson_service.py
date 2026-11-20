"""Lessons on the digital board: their blocks become searchable text,
publishing makes them visible to the class's students, and a student (or a
guardian) consults their class's published lessons - newest first, by
subject, searchable.

The class, subject and enrolment are academica's; "own" comes from
academica.services.portal_service (the signed-in user's student or guardian
Person), never from the client.
"""
import re

from django.db.models import Q
from django.utils import timezone

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.core.exceptions import ResaasAPIException

from pedagogica.models import Lesson

BLOCK_TYPES = {"text", "image", "document", "diagram", "drawing"}
_TAGS = re.compile(r"<[^>]+>")


def clean_blocks(blocks):
    """The blocks as stored: a list of {"type", "content"?, "attachment"?,
    "caption"?} of the known types (400 otherwise)."""
    if blocks in (None, ""):
        return []
    if not isinstance(blocks, list):
        raise ResaasAPIException("The lesson's content is not valid.", code="invalid", details={"blocks": ["A list."]})
    cleaned = []
    for block in blocks:
        if not isinstance(block, dict) or block.get("type") not in BLOCK_TYPES:
            raise ResaasAPIException("The lesson's content is not valid.", code="invalid",
                                     details={"blocks": ["Unknown block."]})
        cleaned.append({k: block[k] for k in ("type", "content", "attachment", "caption") if k in block})
    return cleaned


def search_text(title, summary, blocks):
    parts = [title or "", summary or ""]
    for block in blocks or []:
        if block.get("type") in ("text", "diagram"):
            parts.append(_TAGS.sub(" ", str(block.get("content") or "")))
        if block.get("caption"):
            parts.append(str(block["caption"]))
    return re.sub(r"\s+", " ", " ".join(parts)).strip()[:20000]


def publish(*, lesson, user):
    if lesson.status != Lesson.STATUS_PUBLISHED:
        lesson.status = Lesson.STATUS_PUBLISHED
        lesson.published_at = timezone.now()
        lesson.updated_by = user
        lesson.save(update_fields=["status", "published_at", "updated_by", "updated_at"])
        EventDispatcher.emit("pedagogica.lesson.published", instance=lesson, actor=user,
                             context={"lesson_id": str(lesson.id), "class_group_id": str(lesson.class_group_id)})
    return lesson


def unpublish(*, lesson, user):
    if lesson.status != Lesson.STATUS_DRAFT:
        lesson.status = Lesson.STATUS_DRAFT
        lesson.updated_by = user
        lesson.save(update_fields=["status", "updated_by", "updated_at"])
    return lesson


def search(queryset, q):
    """Lessons matching every word of `q` in the title, summary or content."""
    for word in (q or "").split():
        queryset = queryset.filter(Q(title__icontains=word) | Q(summary__icontains=word) | Q(search_text__icontains=word))
    return queryset


def for_enrolment(enrolment, *, subject_id=None, q=None):
    """The published lessons of an enrolment's class, newest first."""
    if not enrolment.class_group_id:
        return Lesson.objects.none()
    lessons = Lesson.objects.filter(class_group_id=enrolment.class_group_id, status=Lesson.STATUS_PUBLISHED)
    if subject_id:
        lessons = lessons.filter(subject_id=subject_id)
    return search(lessons.select_related("subject", "teacher__person").prefetch_related("attachments"), q)
