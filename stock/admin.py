
from django_resaas.core.base.admin import BaseAdmin
from django.contrib import admin

admin.site.site_title = 'Stock'
admin.site.index_title = 'Stock'

def all_fields(model):
    return [field.name for field in model._meta.fields]


