from django.contrib import admin

from django_resaas.saas.core.base.admin import BaseAdmin, all_fields

from catalog.models import Product, ProductCategory, ProductMedia


@admin.register(ProductCategory)
class ProductCategoryAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


@admin.register(Product)
class ProductAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


@admin.register(ProductMedia)
class ProductMediaAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)
