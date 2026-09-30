from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class JobPosition(BaseModel):
    title = models.CharField(max_length=150)
    code = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    department = models.ForeignKey(
        'hr.Department',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='positions'
    )

    class Meta:
        ordering = ['title']
        unique_together = ('entity', 'title')

    class RESAAS:
        label_field = "title"
        search_fields = ["code", "title"]
        crud = True
        routes={
            'list': "list_jobposition",
            'view': "view_jobposition",
            'add': "add_jobposition",
            'change': "change_jobposition"
        }


    def __str__(self):
        return self.title