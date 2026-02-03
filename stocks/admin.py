from django.contrib import admin
from .models import ProductCategory, Supplier, Customer, Product

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'contact_person', 'type', 'vat', 'payment_term')
    search_fields = ('company_name', 'contact_person')

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'contact_person', 'payment_term')
    search_fields = ('company_name', 'contact_person')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # แก้ไขชื่อ Field ให้ตรงกับ models.py (เปลี่ยน sku -> barcode, price -> buy_price)
    list_display = ('name', 'barcode', 'buy_price', 'sale_price', 'stock_quantity', 'unit', 'has_bom')
    search_fields = ('name', 'barcode')
    list_filter = ('category', 'has_bom', 'supplier')
