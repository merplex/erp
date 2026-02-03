from django.contrib import admin
from django.utils.html import format_html
from .models import *

# --- Inline Tables ---
class BOMIngredientInline(admin.TabularInline):
    model = BOMIngredient
    fields = ('material', 'quantity', 'get_unit_display') 
    readonly_fields = ('get_unit_display',)
    autocomplete_fields = ['material']
    extra = 1
    def get_unit_display(self, obj): return obj.get_unit
    get_unit_display.short_description = "หน่วย"

class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1

class SalesItemInline(admin.TabularInline):
    model = SalesItem
    extra = 1

# --- ฟังก์ชันช่วยแสดงสีของส่วนต่าง ---
def color_diff(diff):
    color = "green" if diff >= 0 else "red"
    prefix = "+" if diff > 0 else ""
    return format_html('<span style="color: {}; font-weight: bold;">{}{}{}</span>', color, prefix, diff, " ชิ้น" if diff != 0 else "")

# --- Admin Registration ---
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
    list_display = ('name', 'barcode', 'buy_price', 'sale_price', 'stock_quantity', 'unit', 'has_bom')
    search_fields = ('name', 'barcode')
    list_filter = ('category', 'has_bom', 'supplier')

@admin.register(BOM)
class BOMAdmin(admin.ModelAdmin):
    list_display = ('name', 'product', 'total_cost_display', 'sale_price', 'unit', 'production_time', 'created_by')
    inlines = [BOMIngredientInline]
    readonly_fields = ('created_by', 'updated_by')
    def total_cost_display(self, obj): return f"{obj.total_cost:,.2f}"
    total_cost_display.short_description = "ต้นทุนรวม (บาท)"
    def save_model(self, request, obj, form, change):
        if not change: obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

# --- ส่วนของประวัติ ซื้อ/ขาย/ผลิต ---
@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('po_number', 'supplier', 'order_date', 'status', 'diff_summary')
    list_filter = ('status', 'order_date', 'supplier')
    search_fields = ('po_number', 'invoice_no_supplier')
    inlines = [PurchaseItemInline]
    def diff_summary(self, obj):
        diff = sum(i.quantity_received - i.quantity_ordered for i in obj.items.all())
        return color_diff(diff)
    diff_summary.short_description = "ยอดต่างรวม"

@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ('so_number', 'customer', 'order_date', 'status', 'diff_summary')
    list_filter = ('status', 'order_date', 'customer')
    search_fields = ('so_number', 'po_no_customer')
    inlines = [SalesItemInline]
    def diff_summary(self, obj):
        diff = sum(i.quantity_shipped - i.quantity_ordered for i in obj.items.all())
        return color_diff(diff)
    diff_summary.short_description = "ยอดต่าง (ปรับยอด)"

@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = ('pd_number', 'product', 'order_date', 'status', 'diff_status')
    list_filter = ('status', 'order_date', 'product')
    def diff_status(self, obj):
        diff = obj.quantity_actual - obj.quantity_planned
        return color_diff(diff)
    diff_status.short_description = "ยอดต่างผลิต"
