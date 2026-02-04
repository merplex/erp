from django.contrib import admin
from django.utils.html import format_html
from django.core.exceptions import ValidationError
from .models import *

# --- Inlines ---
class ProductSupplierInline(admin.TabularInline):
    model = ProductSupplier
    extra = 1

# นี่คือส่วนที่เปรมขอ: แสดงสินค้าใต้ Supplier
class SupplierProductInline(admin.TabularInline):
    model = ProductSupplier
    extra = 1
    autocomplete_fields = ['product']
    fields = ('product', 'supplier_sku', 'latest_buy_price')

class BOMIngredientInline(admin.TabularInline):
    model = BOMIngredient
    fields = ('material', 'quantity', 'get_unit_display')
    readonly_fields = ('get_unit_display',)
    autocomplete_fields = ['material']
    model = BOMIngredient
    extra = 1
    def get_unit_display(self, obj): return obj.get_unit
    get_unit_display.short_description = "หน่วย"

class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            parent_id = request.resolver_match.kwargs.get('object_id')
            if parent_id:
                po = PurchaseOrder.objects.get(pk=parent_id)
                kwargs["queryset"] = Product.objects.filter(product_suppliers__supplier=po.supplier)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class PurchaseReceiptLogInline(admin.TabularInline):
    model = PurchaseReceiptLog
    extra = 1
    readonly_fields = ('received_date', 'user')

class SalesItemInline(admin.TabularInline):
    model = SalesItem
    extra = 1

class SalesDeliveryLogInline(admin.TabularInline):
    model = SalesDeliveryLog
    extra = 1
    readonly_fields = ('shipped_date', 'user')

class ProductionLogInline(admin.TabularInline):
    model = ProductionLog
    extra = 1
    readonly_fields = ('finished_date', 'user')

# --- Helper ---
def color_diff(diff):
    color = "green" if diff >= 0 else "red"
    prefix = "+" if diff > 0 else ""
    return format_html('<span style="color: {}; font-weight: bold;">{}{}{}</span>', color, prefix, diff, " ชิ้น" if diff != 0 else "")

# --- Admin Registrations ---

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'contact_person', 'type')
    inlines = [SupplierProductInline] # เพิ่ม Inline ตัวที่เปรมขอที่นี่ค่ะ

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'barcode', 'buy_price', 'sale_price', 'stock_quantity', 'unit', 'has_bom', 'created_by', 'updated_by')
    list_filter = ('category', 'has_bom', 'suppliers')
    search_fields = ('name', 'barcode')
    inlines = [ProductSupplierInline]
    readonly_fields = ('created_by', 'updated_by', 'created_at', 'updated_at')

    # Logic: บันทึก User อัตโนมัติ (ใครพิมพ์คนนั้นเป็นคนสร้าง/แก้)
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
            obj.updated_by = request.user
        else:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    # Logic: ตรวจสอบความสัมพันธ์ BOM กับ Lead Time
    def clean_fields(self, request, obj):
        if obj.has_bom and (obj.production_lead_time is None or obj.production_lead_time <= 0):
            raise ValidationError({'production_lead_time': "เนื่องจากเป็นสินค้า BOM กรุณาระบุระยะเวลาผลิตด้วยค่ะ"})
        return super().clean_fields(request, obj)

@admin.register(BOM)
class BOMAdmin(admin.ModelAdmin):
    list_display = ('name', 'product', 'total_cost_display', 'sale_price', 'unit', 'production_time', 'created_by')
    list_filter = ('product__category',)
    inlines = [BOMIngredientInline]
    readonly_fields = ('created_by', 'updated_by')
    def total_cost_display(self, obj): return f"{obj.total_cost:,.2f}"
    
    def save_model(self, request, obj, form, change):
        if not change: obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

# --- กลุ่ม B: Orders ---

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('po_number', 'supplier', 'order_date', 'status', 'get_diff')
    list_filter = ('status', 'order_date', 'supplier')
    search_fields = ('po_number', 'invoice_no_supplier')
    inlines = [PurchaseItemInline, PurchaseReceiptLogInline]
    def get_diff(self, obj):
        ordered = sum(i.quantity_ordered for i in obj.items.all())
        received = sum(l.quantity_received for l in obj.receipt_logs.all())
        return color_diff(received - ordered)
    get_diff.short_description = "ยอดต่างรับเข้า"

@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ('so_number', 'customer', 'order_date', 'status', 'get_diff')
    list_filter = ('status', 'order_date', 'customer')
    inlines = [SalesItemInline, SalesDeliveryLogInline]
    def get_diff(self, obj):
        ordered = sum(i.quantity_ordered for i in obj.items.all())
        shipped = sum(l.quantity_shipped for l in obj.delivery_logs.all())
        return color_diff(shipped - ordered)

@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = ('pd_number', 'product', 'order_date', 'status', 'get_diff')
    list_filter = ('status', 'order_date', 'product')
    inlines = [ProductionLogInline]
    def get_diff(self, obj):
        planned = obj.quantity_planned
        actual = sum(l.quantity_finished for l in obj.production_logs.all())
        return color_diff(actual - planned)

# --- กลุ่ม C: Planning & Finance (ตารางแยก) ---

@admin.register(StockPlanning)
class StockPlanningAdmin(admin.ModelAdmin):
    list_display = ('name', 'stock_quantity', 'show_available')
    def show_available(self, obj):
        # เดี๋ยวเรามาใส่สูตรคำนวณในสเต็ปถัดไปนะคะ ตอนนี้โชว์ยอดสต็อกไปก่อน
        return obj.stock_quantity
    show_available.short_description = "ยอดพร้อมใช้ (Available)"

@admin.register(FinanceReport)
class FinanceReportAdmin(admin.ModelAdmin):
    list_display = ('po_number', 'supplier', 'order_date', 'status')

# --- ลงทะเบียนตารางที่เหลือ ---
# --- ลงทะเบียนที่เหลือ (ต้องมีแค่ตัวที่ไม่ได้ใช้ @admin.register ข้างบน) ---

admin.site.register(ProductCategory)
admin.site.register(Customer)
