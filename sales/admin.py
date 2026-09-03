from django_resaas.engine.core.base.admin import BaseAdmin, all_fields
from django.contrib import admin

from sales.models.customer import Customer
from sales.models.customercontact import CustomerContact
from sales.models.sale import Sale
from sales.models.saleitem import SaleItem
from sales.models.payment import Payment


@admin.register(Customer)
class CustomerAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


@admin.register(CustomerContact)
class CustomerContactAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


@admin.register(Sale)
class SaleAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


@admin.register(SaleItem)
class SaleItemAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)


@admin.register(Payment)
class PaymentAdmin(BaseAdmin):
    def get_list_display(self, request): return all_fields(self.model)
    list_display = ("id",)
