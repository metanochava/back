from django.db import models

from django_resaas.saas.core.base.models import BaseModel
from django_resaas.saas.core.utils import upload_path


class LessonPlan(BaseModel):
    """What a teacher plans to teach a class in a subject (objectives, content,
    activities, resources); a lesson can follow it."""

    STATUS_DRAFT = "draft"
    STATUS_READY = "ready"
    STATUS_CHOICES = ((STATUS_DRAFT, "Draft"), (STATUS_READY, "Ready"))

    class_group = models.ForeignKey("academica.ClassGroup", on_delete=models.CASCADE, related_name="lesson_plans")
    subject = models.ForeignKey("academica.Subject", on_delete=models.PROTECT, related_name="lesson_plans")
    teacher = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="lesson_plans")
    period = models.ForeignKey("academica.AcademicPeriod", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="lesson_plans")
    title = models.CharField(max_length=160)
    planned_for = models.DateField(null=True, blank=True)
    objectives = models.TextField(blank=True, default="")
    content = models.TextField(blank=True, default="")
    activities = models.TextField(blank=True, default="")
    resources = models.TextField(blank=True, default="")
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    class Meta:
        verbose_name = "Lesson plan"
        verbose_name_plural = "Lesson plans"
        ordering = ["-planned_for", "-created_at"]

    class RESAAS:
        label_field = "title"
        search_fields = ["title", "objectives", "subject__name", "class_group__name"]
        crud = True


class Lesson(BaseModel):
    """A lesson as written on the digital board: the explanation in ordered
    blocks (text, image, document, diagram, drawing), with its date, subject
    and class. Published, the class's students consult it later; searchable
    (search_text: the blocks' text)."""

    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_CHOICES = ((STATUS_DRAFT, "Draft"), (STATUS_PUBLISHED, "Published"))

    class_group = models.ForeignKey("academica.ClassGroup", on_delete=models.CASCADE, related_name="lessons")
    subject = models.ForeignKey("academica.Subject", on_delete=models.PROTECT, related_name="lessons")
    teacher = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="lessons")
    plan = models.ForeignKey(LessonPlan, null=True, blank=True, on_delete=models.SET_NULL, related_name="lessons")
    date = models.DateField()
    title = models.CharField(max_length=160)
    summary = models.TextField(blank=True, default="")
    # [{"type": "text"|"image"|"document"|"diagram"|"drawing", "content": ..., "attachment": <id>?, "caption": ...}]
    blocks = models.JSONField(default=list, blank=True)
    search_text = models.TextField(blank=True, default="", editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT, editable=False)
    published_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Lesson"
        verbose_name_plural = "Lessons"
        ordering = ["-date", "-created_at"]
        indexes = [models.Index(fields=["class_group", "subject", "date"], name="pedagogica_lesson_class_date")]

    class RESAAS:
        label_field = "title"
        search_fields = ["title", "summary", "search_text", "subject__name", "class_group__name"]
        crud = True


class LessonAttachment(BaseModel):
    """An image, document or drawing used by a lesson's blocks."""

    KIND_IMAGE = "image"
    KIND_DOCUMENT = "document"
    KIND_DRAWING = "drawing"
    KIND_CHOICES = ((KIND_IMAGE, "Image"), (KIND_DOCUMENT, "Document"), (KIND_DRAWING, "Drawing"))

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="attachments")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_IMAGE)
    file = models.FileField(upload_to=upload_path("pedagogica/lessons"), max_length=500)
    caption = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "Lesson attachment"
        verbose_name_plural = "Lesson attachments"
        ordering = ["created_at"]

    class RESAAS:
        label_field = "caption"
        crud = True
        fields = {"file": {"accept": ".png,.jpg,.jpeg,.webp,.gif,.svg,.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt",
                           "max_size": 30 * 1024 * 1024, "multiple": False}}
