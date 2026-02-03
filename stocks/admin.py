from django.contrib import admin
from .models import ProductCategory, Supplier, Customer, Product , BOM, BOMIngredient

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

# ส่วนแสดงผลวัตถุดิบแบบบรรทัด (Inline)
class BOMIngredientInline(admin.TabularInline):
    model = BOMIngredient
    extra = 1 # ให้โชว์แถวว่างไว้ 1 แถวเสมอ
    autocomplete_fields = ['material'] # ช่วยให้ค้นหาวัตถุดิบได้เร็วขึ้น

@admin.register(BOM)
class BOMAdmin(admin.ModelAdmin):
    list_display = ('name', 'product', 'total_cost_display', 'sale_price', 'production_time', 'created_by')
    inlines = [BOMIngredientInline] # ดึงตารางวัตถุดิบมาไว้ด้านล่าง
    readonly_fields = ('created_by', 'updated_by')

    def total_cost_display(self, obj):
        return f"{obj.total_cost:,.2f}"
    total_cost_display.short_description = "ต้นทุนรวม (บาท)"

    def save_model(self, request, obj, form, change):
        if not change: # ถ้าเป็นการสร้างครั้งแรก
            obj.created_by = request.user
        obj.updated_by = request.user # เก็บชื่อคนแก้ไขล่าสุดเสมอ
        super().save_model(request, obj, form, change)
