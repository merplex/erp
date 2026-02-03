from django.contrib import admin
from .models import Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # กำหนดคอลัมน์ที่จะโชว์ในหน้าลิสต์
    list_display = ('name', 'sku', 'price', 'sale_price', 'stock_quantity', 'unit')
    # เพิ่มช่องค้นหา
    search_fields = ('name', 'sku', 'barcode')
