from django.contrib import admin
from django.utils.html import format_html
from django.core.exceptions import ValidationError
from django.forms import TextInput # อย่าลืม Import ตัวนี้ไว้บนสุดของ admin.py นะคะ
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
    # เพิ่มบรรทัดนี้ครับ ยอดสะสมจะกลายเป็นตัวหนังสือสีเทาที่อ่านได้อย่างเดียว แก้ไม่ได้
    readonly_fields = ('quantity_received',) 

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            # หา ID ของใบสั่งซื้อปัจจุบัน
            resolved = request.resolver_match
            if resolved and 'object_id' in resolved.kwargs:
                po_id = resolved.kwargs['object_id']
                po = PurchaseOrder.objects.get(pk=po_id)
                # กรองสินค้า: ต้องเป็นสินค้าที่มีชื่อ Supplier คนนี้ผูกอยู่เท่านั้น
                kwargs["queryset"] = Product.objects.filter(product_suppliers__supplier=po.supplier)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class PurchaseReceiptLogInline(admin.TabularInline):
    model = PurchaseReceiptLog
    extra = 1
    fields = ('product', 'supplier_invoice', 'quantity_received', 'user', 'notes', 'received_date')
    readonly_fields = ('user', 'received_date')

    # --- ส่วนที่เพิ่มเพื่อบีบหน้าจอ ---
    formfield_overrides = {
        # บีบช่อง Invoice (CharField) ให้เหลือ 1/4 (ประมาณ 100-120px)
        models.CharField: {'widget': TextInput(attrs={'style': 'width: 120px;', 'placeholder': 'เลขใบส่งของ'})},
        # เปลี่ยนช่อง Note (TextField) จากกล่องใหญ่เป็นบรรทัดเดียว (TextInput) ยาว 80 ตัวอักษร
        models.TextField: {'widget': TextInput(attrs={'style': 'width: 200px;', 'placeholder': 'หมายเหตุ'})},
    }
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            resolved = request.resolver_match
            if resolved and 'object_id' in resolved.kwargs:
                po_id = resolved.kwargs['object_id']
                # กรองสินค้า: ต้องเป็นสินค้าที่มีอยู่ในรายการ PurchaseItem ของ PO นี้เท่านั้น
                kwargs["queryset"] = Product.objects.filter(purchaseitem_order_id=po_id).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class SalesItemInline(admin.TabularInline):
    model = SalesItem
    extra = 1
    readonly_fields = ('quantity_shipped',)

class SalesDeliveryLogInline(admin.TabularInline):
    model = SalesDeliveryLog
    extra = 1
    fields = ('product','shipping_no', 'quantity_shipped', 'user', 'notes','shipped_date')
    readonly_fields = ('user', 'shipped_date')
    # --- ส่วนที่เพิ่มเพื่อบีบหน้าจอ ---
    formfield_overrides = {
        # บีบช่อง Invoice (CharField) ให้เหลือ 1/4 (ประมาณ 100-120px)
        models.CharField: {'widget': TextInput(attrs={'style': 'width: 120px;', 'placeholder': 'เลขใบส่งของ'})},
        # เปลี่ยนช่อง Note (TextField) จากกล่องใหญ่เป็นบรรทัดเดียว (TextInput) ยาว 80 ตัวอักษร
        models.TextField: {'widget': TextInput(attrs={'style': 'width: 200px;', 'placeholder': 'หมายเหตุ'})},
    }

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            resolved = request.resolver_match
            if resolved and 'object_id' in resolved.kwargs:
                so_id = resolved.kwargs['object_id']
                # กรองสินค้า: ต้องเป็นสินค้าที่มีอยู่ในรายการ SalesItem ของ SO นี้เท่านั้น
                kwargs["queryset"] = Product.objects.filter(salesitem__sales_order_id=so_id).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class ProductionLogInline(admin.TabularInline):
    model = ProductionLog
    extra = 1
    fields = ('quantity_finished', 'user','notes', 'finished_date')
    readonly_fields = ('user', 'finished_date')
    # --- ส่วนที่เพิ่มเพื่อบีบหน้าจอ ---
    formfield_overrides = {
        # บีบช่อง Invoice (CharField) ให้เหลือ 1/4 (ประมาณ 100-120px)
        models.CharField: {'widget': TextInput(attrs={'style': 'width: 120px;', 'placeholder': 'เลขใบส่งของ'})},
        # เปลี่ยนช่อง Note (TextField) จากกล่องใหญ่เป็นบรรทัดเดียว (TextInput) ยาว 80 ตัวอักษร
        models.TextField: {'widget': TextInput(attrs={'style': 'width: 200px;', 'placeholder': 'หมายเหตุ'})},
    }

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
    # เพิ่ม 'get_diff' เข้าไปในรายการโชว์หน้า List
    list_display = ('po_number', 'supplier', 'order_date', 'status', 'get_diff')
    list_filter = ('status', 'order_date', 'supplier')
    search_fields = ('po_number', 'invoice_no_supplier', 'supplier__company_name')
    inlines = [PurchaseItemInline, PurchaseReceiptLogInline]
    readonly_fields = ('created_by', 'status') # เพิ่ม status เข้าไปตรงนี้

    # เพิ่มฟังก์ชันนี้เพื่อดึงชื่อคนล็อกอินมาบันทึกอัตโนมัติ
    def save_model(self, request, obj, form, change):
        if not change: # ถ้าเป็นการสร้างใหม่
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    # ฟังก์ชันคำนวณส่วนต่าง (รับจริง vs สั่งซื้อ)
    def get_diff(self, obj):
        ordered = sum(i.quantity_ordered for i in obj.items.all())
        received = sum(l.quantity_received for l in obj.receipt_logs.all())
        return color_diff(received - ordered)
    get_diff.short_description = "สถานะรับของ"

    # ฟังก์ชันบันทึก User อัตโนมัติในตาราง Log
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if hasattr(instance, 'user'): instance.user = request.user
            instance.save()
        formset.save_m2m()

@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ('so_number', 'customer', 'order_date', 'status', 'get_diff')
    list_filter = ('status', 'order_date', 'customer')
    search_fields = ('so_number', 'po_no_customer', 'customer__company_name')
    inlines = [SalesItemInline, SalesDeliveryLogInline]
    readonly_fields = ('created_by',) 
    
    # เพิ่มฟังก์ชันนี้เพื่อดึงชื่อคนล็อกอินมาบันทึกอัตโนมัติ
    def save_model(self, request, obj, form, change):
        if not change: # ถ้าเป็นการสร้างใหม่
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    # คำนวณส่วนต่าง (ส่งจริง vs สั่งขาย)
    def get_diff(self, obj):
        ordered = sum(i.quantity_ordered for i in obj.items.all())
        shipped = sum(l.quantity_shipped for l in obj.delivery_logs.all())
        return color_diff(shipped - ordered)
    get_diff.short_description = "สถานะส่งของ"

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if hasattr(instance, 'user'): instance.user = request.user
            instance.save()
        formset.save_m2m()

@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = ('pd_number', 'product', 'quantity_planned', 'quantity_actual', 'get_diff', 'status')
    list_filter = ('status', 'order_date', 'product')
    search_fields = ('pd_number', 'product__name')
    inlines = [ProductionLogInline]
    readonly_fields = ('created_by',) 

    # เพิ่มฟังก์ชันนี้เพื่อดึงชื่อคนล็อกอินมาบันทึกอัตโนมัติ
    def save_model(self, request, obj, form, change):
        if not change: # ถ้าเป็นการสร้างใหม่
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    # คำนวณส่วนต่าง (ผลิตได้จริง vs แผนผลิต)
    def get_diff(self, obj):
        planned = obj.quantity_planned
        actual = obj.quantity_actual
        return color_diff(actual - planned)
    get_diff.short_description = "สถานะผลิต"

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if hasattr(instance, 'user'): instance.user = request.user
            instance.save()
        formset.save_m2m()

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
