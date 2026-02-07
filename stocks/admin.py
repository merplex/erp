from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.widgets import AdminDateWidget
from django.contrib.admin import helpers  # <--- helpers ต้องดึงมาจาก admin ครับ
from django.utils.html import format_html
from django.core.exceptions import ValidationError
from django.forms import TextInput
from django.db import models # เพิ่มเพื่อรองรับ formfield_overrides
from .models import *
from django import forms # ✅ เพิ่มบรรทัดนี้ครับ ทำระบบ tag checkbox
from django.db.models import F
from django.utils.safestring import mark_safe # ✅ ต้องมีบรรทัดนี้ครับ
# เพิ่มที่บรรทัดบนสุดของไฟล์ครับ
from django.http import HttpResponseRedirect
from django.template import Template, RequestContext 
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse

class ProductOnlyFilter(admin.SimpleListFilter):
    title = 'ประเภทรายการ' # หัวข้อบนแถบ Filter
    parameter_name = 'is_product'

    def lookups(self, request, model_admin):
        return (
            ('true', 'สินค้าเท่านั้น'),
            ('false', 'ไม่ใช่สินค้า (ค่าบริการ/อื่นๆ)'),
            ('all', 'แสดงทั้งหมด'),
        )

    def queryset(self, request, queryset):
        # ✅ กำหนด Logic การกรอง
        if self.value() == 'true':
            return queryset.filter(is_product=True)
        if self.value() == 'false':
            return queryset.filter(is_product=False)
        if self.value() == 'all':
            return queryset
        
        # 🎯 จุดสำคัญ: ถ้ายังไม่ได้เลือก (Default) ให้โชว์แค่สินค้า
        if self.value() is None:
            return queryset.filter(is_product=True)
        
        return queryset

# ✅ 1. Inline รายการสินค้า (แบบ Read-Only สำหรับหน้าการเงิน)
class PurchaseItemReadOnlyInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0
    can_delete = False # ห้ามลบรายการ
    verbose_name = "🛒 รายการสินค้า (ตรวจสอบราคา)"
    verbose_name_plural = "🛒 รายการสินค้า (Read-Only)"
    
    # โชว์ครบ: สินค้า, จำนวน, ราคาต่อหน่วย (ที่ล็อกแล้ว), ราคารวมบรรทัด
    fields = ('product', 'quantity_ordered', 'unit_price', 'get_line_total')
    readonly_fields = ('product', 'quantity_ordered', 'unit_price', 'get_line_total')

    def get_line_total(self, obj):
        return f"{obj.total_price:,.2f}"
    get_line_total.short_description = "ราคารวม"

    def has_add_permission(self, request, obj=None): return False

# ✅ เพิ่มอันนี้เข้าไปครับ: ตารางแสดงรายการสินค้า (แบบดูได้อย่างเดียว)
class SalesItemReadOnlyInline(admin.TabularInline):
    model = SalesItem  # ชื่อ Model สินค้าฝั่งขาย (เช็คใน models.py ว่าชื่อนี้ไหม)
    extra = 0
    fields = ['product', 'quantity_ordered', 'sale_price', 'get_total_display', 'auto_produce']
    readonly_fields = ['product', 'quantity_ordered', 'sale_price', 'get_total_display', 'auto_produce']
    can_delete = False
    verbose_name = "📦 รายการสินค้าที่ขาย"
    verbose_name_plural = "รายการสินค้า"
    
    def has_add_permission(self, request, obj):
        return False
    
    def get_unit_price(self, obj):
        # ใช้ sale_price ตามที่เปรมบอก
        price = obj.product.sale_price if obj.product else 0 
        return f"{price:,.2f}"
    get_unit_price.short_description = "ราคาขาย (@)"

    # ✅ คำนวณยอดรวม (จำนวนที่สั่ง x ราคาขาย)
    def get_line_total(self, obj):
        price = obj.product.sale_price if obj.product else 0
        total = price * obj.quantity_ordered
        return f"{total:,.2f}"
    get_line_total.short_description = "รวมเงิน"

    def get_total_display(self, obj):
        # คำนวณ: จำนวน x ราคาขาย
        price = obj.sale_price or 0
        qty = obj.quantity_ordered or 0
        total = price * qty
        return f"{total:,.2f}"
    
    get_total_display.short_description = "ราคารวม"
    
# ✅ 2. Inline การจ่ายเงิน และการรับเงิน (บันทึกยอดได้เรื่อยๆ)
class PurchasePaymentInline(admin.TabularInline):
    model = PurchasePaymentLog
    extra = 1
    verbose_name = "💰 บันทึกการจ่ายเงิน"
    verbose_name_plural = "💰 ประวัติการจ่ายเงิน (Payments)"
    fields = ('amount', 'notes', 'payment_date', 'user')
    readonly_fields = ('payment_date', 'user')


class SalesPaymentInline(admin.TabularInline):
    model = SalesPayment
    extra = 1
    verbose_name = "💰 รายการรับเงิน"
    verbose_name_plural = "ประวัติการรับเงิน (กรอกเองกรณีแบ่งจ่าย / หรือกด Action หน้ารวมเพื่อรับเต็มจำนวน)"
    fields = ('payment_date', 'amount', 'remark', 'evidence')
# ---------------------------------------------------------
# Inline แสดงรายการสินค้าในหน้ากลุ่มสินค้า (Category)
# ---------------------------------------------------------
class ProductInCategoryInline(admin.TabularInline):
    model = Product
    fields = ['get_barcode', 'buy_price', 'sale_price', 'stock_quantity', 'unit']
    readonly_fields = fields # ให้ดูอย่างเดียว ไม่ให้แก้จากหน้านี้เพื่อความปลอดภัย
    extra = 0
    can_delete = False
    verbose_name = "📦 สินค้าในกลุ่มนี้"
    verbose_name_plural = "📦 รายการสินค้าทั้งหมดในกลุ่ม"

    def has_add_permission(self, request, obj=None): return False

    # ✅ เพิ่มฟังก์ชันนี้เพื่อดึงบาร์โค้ดมาแสดงในตาราง
    def get_barcode(self, obj):
        return obj.latest_barcode # ใช้ property ที่เราเขียนไว้ใน models.py
    get_barcode.short_description = "บาร์โค้ด (ล่าสุด)"

    def has_add_permission(self, request, obj=None): 
        return False
# ---------------------------------------------------------
# 1. สร้าง Inline สำหรับแสดงสินค้าที่ใช้แท็กนี้
# ---------------------------------------------------------
class ProductInTagInline(admin.TabularInline):
    # ใช้ table กลางของ ManyToMany ระหว่าง Product และ Tags
    model = Product.tags.through 
    extra = 0
    verbose_name = "สินค้าที่ใช้แท็กนี้"
    verbose_name_plural = "รายการสินค้าทั้งหมดที่ใช้แท็กนี้"
    
    # ปรับให้ดูอย่างเดียว (Read-only) เพื่อความปลอดภัย ไม่ให้เผลอลบสินค้าจากหน้านี้
    readonly_fields = ('product',)
    can_delete = False
    
    def has_add_permission(self, request, obj=None): 
        return False
    
    # ✅ แสดงฟิลด์ตามที่เปรมต้องการ
    fields = ('get_product_name', 'get_barcode', 'get_buy_price', 'get_sale_price', 'get_stock')
    readonly_fields = ('get_product_name', 'get_barcode', 'get_buy_price', 'get_sale_price', 'get_stock')

    def get_product_name(self, obj):
        # ใน ManyToMany Inline ต้องเข้าผ่าน obj.product นะครับ
        return obj.product.name
    get_product_name.short_description = "ชื่อสินค้า"

    def get_barcode(self, obj):
        # ✅ ดึงบาร์โค้ดล่าสุด (Last ID) ตามที่เปรมออกแบบไว้
        barcode = obj.product.barcodes.order_by('-id').first()
        return barcode.code if barcode else "-"
    get_barcode.short_description = "บาร์โค้ดล่าสุด"

    def get_buy_price(self, obj):
        return f"{obj.product.buy_price:,.2f}"
    get_buy_price.short_description = "ราคาทุน"

    def get_sale_price(self, obj):
        return f"{obj.product.sale_price:,.2f}"
    get_sale_price.short_description = "ราคาขาย"

    def get_stock(self, obj):
        # ✅ แสดงสต็อกปัจจุบันพร้อมหน่วย
        return f"{obj.product.stock_quantity} {obj.product.unit}"
    get_stock.short_description = "สต็อกปัจจุบัน"
# ---------------------------------------------------------
# 1. รายการสั่งซื้อ (ค้างรับ) -> ใช้ po_number และติดลบ
# ---------------------------------------------------------
class PendingPurchaseInline(admin.TabularInline):
    model = PurchaseItem
    fields = ['get_ref_no', 'quantity_ordered', 'quantity_received', 'get_pending']
    readonly_fields = fields
    extra = 0
    can_delete = False
    verbose_name = "🛒 รายการสั่งซื้อ (ค้างรับ)"
    verbose_name_plural = "🛒 รายการสั่งซื้อค้างรับ"

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            quantity_ordered__gt=F('quantity_received')
        ).exclude(
            purchase_order__status__in=['Received', 'Completed', 'Cancelled']
        )

    def get_ref_no(self, obj):
        # ✅ แก้จาก obj.order เป็น obj.purchase_order ตามโครงสร้างเปรม
        return obj.purchase_order.po_number 
    get_ref_no.short_description = "PO No."

    def get_pending(self, obj):
        diff = obj.quantity_ordered - obj.quantity_received
        return format_html('<b style="color:#dc3545;">-{}</b>', diff)
    get_pending.short_description = "ขาดรับ"

    def has_add_permission(self, request, obj=None): return False

# ---------------------------------------------------------
# 2. รายการผลิต (ค้างผลิต) -> ใช้ pd_number
# ---------------------------------------------------------
class PendingProductionInline(admin.TabularInline):
    model = ProductionOrder
    fields = ['pd_number', 'quantity_planned', 'quantity_actual', 'get_pending']
    readonly_fields = fields
    extra = 0
    can_delete = False
    verbose_name = "🔨 รายการผลิต (ค้างผลิต)"
    verbose_name_plural = "🔨 รายการผลิตค้างผลิต"

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            quantity_planned__gt=F('quantity_actual') # ✅ ยังไม่ครบจำนวน
        ).exclude(
            status__in=['Finished', 'Completed', 'Cancelled'] # ✅ และยังไม่จบงาน/ยกเลิก
        )

    def get_pending(self, obj):
        diff = obj.quantity_planned - obj.quantity_actual
        return format_html('<b style="color:#dc3545;">-{}</b>', diff)
    get_pending.short_description = "ขาดผลิต"

    def has_add_permission(self, request, obj=None): return False

# ---------------------------------------------------------
# 3. รายการขาย (ค้างส่ง) -> ใช้ so_number
# ---------------------------------------------------------
class PendingSaleInline(admin.TabularInline):
    model = SalesItem
    fields = ['sales_order_link','quantity_ordered', 'quantity_shipped', 'get_pending','order_status']
    readonly_fields = fields
    extra = 0
    can_delete = False
    verbose_name = "📦 รายการขาย (ค้างส่ง)"
    verbose_name_plural = "📦 รายการขายค้างส่ง"

    def get_queryset(self, request):
        # ✅ กรองเฉพาะ:
        # 1. ยอดที่สั่งซื้อต้อง "มากกว่า" ยอดที่ส่งไปแล้ว (ยังมีของค้างส่ง)
        # 2. สถานะใบสั่งขายต้องไม่ใช่ 'Shipped' (ส่งครบ), 'Completed' (ปิดงาน), หรือ 'Cancelled' (ยกเลิก)
        return super().get_queryset(request).filter(
            quantity_ordered__gt=F('quantity_shipped')
        ).exclude(
            sales_order__status__in=['Shipped', 'Completed', 'Cancelled']
        )

    def get_pending(self, obj):
        diff = obj.quantity_ordered - obj.quantity_shipped
        return format_html('<b style="color:#dc3545;">-{}</b>', diff)
    get_pending.short_description = "ขาดส่ง"

    def has_add_permission(self, request, obj=None): return False


    # ✅ แถม: ฟังก์ชันโชว์สถานะของใบสั่งขายในตาราง
    def order_status(self, obj):
        status = obj.sales_order.status
        colors = {
            'Draft': '#6c757d',
            'Confirmed': '#007bff',
            'Partially Shipped': '#ffc107',
        }
        color = colors.get(status, '#000')
        return format_html('<b style="color: {};">{}</b>', color, status)
    order_status.short_description = "สถานะใบสั่ง"

    # ✅ แถม: ฟังก์ชันคลิกที่เลขที่ใบสั่งแล้วกระโดดไปหน้าแก้ไขได้เลย
    def sales_order_link(self, obj):
        from django.urls import reverse
        url = reverse("admin:stocks_salesorder_change", args=[obj.sales_order.id])
        return format_html('<a href="{}">{}</a>', url, obj.sales_order.so_number)
    sales_order_link.short_description = "เลขที่ใบสั่งขาย"

# --- Inlines ---
# ---------------------------------------------------------
# Inline สำหรับจัดการหลายบาร์โค้ดในหน้าเดียว
# ---------------------------------------------------------
class ProductBarcodeInline(admin.TabularInline):
    model = ProductBarcode
    extra = 1  # จะมีช่องว่างให้เติม 1 ช่องเสมอ และมีปุ่ม + เพิ่มได้เรื่อยๆ
    verbose_name = "บาร์โค้ดสินค้า"
    verbose_name_plural = "บาร์โค้ดทั้งหมดของสินค้านี้"

class ProductSupplierInline(admin.TabularInline):
    model = ProductSupplier
    extra = 1

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
    extra = 1
    def get_unit_display(self, obj): return obj.get_unit
    get_unit_display.short_description = "หน่วย"

class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    autocomplete_fields = ['product'] 
    extra = 1
    readonly_fields = ('quantity_received',) 

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            # 1. พยายามหา ID จากหลายๆ ช่องทาง (ป้องกันชื่อ ID เปลี่ยน)
            resolved = request.resolver_match
            object_id = None
            if resolved:
                object_id = resolved.kwargs.get('object_id') or resolved.kwargs.get('pk')

            if object_id:
                try:
                    from django.db.models import Q
                    # ✅ ใช้ self.parent_model แทนการระบุชื่อตรงๆ จะปลอดภัยกว่าค่ะ
                    parent_obj = self.parent_model.objects.get(pk=object_id)
                    
                    if parent_obj.supplier:
                        # ✅ กรองสินค้า: 
                        # - เป็นสินค้าที่ Supplier นี้ขาย (ผ่าน product_suppliers)
                        # - หรือ เป็นรายการที่ไม่ใช่สินค้า (is_product=False)
                        kwargs["queryset"] = Product.objects.filter(
                            Q(product_suppliers__supplier=parent_obj.supplier) | 
                            Q(is_product=False)
                        ).distinct()
                    
                except Exception as e:
                    # ถ้ามี Error ให้มันพ่นออกมาใน Console เปรมจะได้เห็นค่ะ
                    print(f"🚨 Filter Error: {e}")
            
            # 💡 ถ้าเป็นหน้า "เพิ่มใหม่" (Add Mode) ซึ่งไม่มี ID 
            # ปกติ Django จะโชว์หมด เพราะมันยังไม่รู้ว่าเปรมจะเลือก Supplier คนไหน
            # ถ้าเปรมอยากให้มันว่างไว้ก่อนจนกว่าจะเลือก ให้ใส่บรรทัดนี้ค่ะ (แต่ต้องกด Save รอบนึงก่อนนะ)
            # elif not object_id:
            #     kwargs["queryset"] = Product.objects.none()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class PurchaseReceiptLogInline(admin.TabularInline):
    model = PurchaseReceiptLog
    extra = 1
    fields = ('product', 'supplier_invoice', 'quantity_received', 'user', 'notes', 'received_date')
    readonly_fields = ('user', 'received_date')

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'style': 'width: 120px;', 'placeholder': 'เลขใบส่งของ'})},
        models.TextField: {'widget': TextInput(attrs={'style': 'width: 200px;', 'placeholder': 'หมายเหตุ'})},
    }
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            resolved = request.resolver_match
            if resolved and 'object_id' in resolved.kwargs:
                po_id = resolved.kwargs['object_id']
                # แก้ไขจากขีดเดียวเป็นสองขีด (__) เพื่อป้องกัน FieldError
                kwargs["queryset"] = Product.objects.filter(purchaseitem__purchase_order_id=po_id).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class SalesItemInline(admin.TabularInline):
    model = SalesItem
    autocomplete_fields = ['product'] 
    extra = 1
    # 1. เรียงลำดับคอลัมน์จากซ้ายไปขวา
    fields = [
        'product',        
        'quantity_ordered', 
        'sale_price',        # ✅ ใส่ตรงนี้เพื่อให้ "แก้ไขได้" (ห้ามใส่ใน readonly_fields)
        'get_total_display', # 🔒 ใส่ตรงนี้เพื่อโชว์ผลลัพธ์ (ต้องใส่ใน readonly_fields ด้วย)
        'auto_produce',      # 🔘 Checkbox อยู่ท้ายสุดตามที่เปรมต้องการ
    ]
    
    # 2. ระบุว่าตัวไหน "ห้ามแก้" (เฉพาะตัวที่คำนวณ)
    readonly_fields = ['get_total_display'] 

    # 3. สร้างฟังก์ชันคำนวณราคารวม (Quantity * Sale Price)
    def get_total_display(self, obj):
        if obj.quantity_ordered and obj.sale_price:
            total = obj.quantity_ordered * obj.sale_price
            return f"{total:,.2f}"
        return "0.00"
    get_total_display.short_description = "ราคารวม"

class SalesDeliveryLogInline(admin.TabularInline):
    model = SalesDeliveryLog
    extra = 1
    fields = ('product','shipping_no', 'quantity_shipped', 'user', 'notes','shipped_date')
    readonly_fields = ('user', 'shipped_date')
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'style': 'width: 120px;', 'placeholder': 'เลขใบส่งของ'})},
        models.TextField: {'widget': TextInput(attrs={'style': 'width: 200px;', 'placeholder': 'หมายเหตุ'})},
    }

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            resolved = request.resolver_match
            if resolved and 'object_id' in resolved.kwargs:
                so_id = resolved.kwargs['object_id']
                kwargs["queryset"] = Product.objects.filter(salesitem__sales_order_id=so_id).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class ProductionLogInline(admin.TabularInline):
    model = ProductionLog
    extra = 1
    fields = ('quantity_finished', 'user','notes', 'finished_date')
    readonly_fields = ('user', 'finished_date')
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'style': 'width: 120px;', 'placeholder': 'เลขใบส่งของ'})},
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
    inlines = [SupplierProductInline]

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_tags', 'get_latest_barcode', 'buy_price', 'get_production_cost', 'sale_price', 'stock_quantity', 'unit', 'has_bom', 'created_by')
    list_filter = ('category','is_product', 'tags', 'has_bom', 'suppliers')
    search_fields = ('name', 'barcodes__code','tags__name')
    inlines = [ProductBarcodeInline, ProductSupplierInline,PendingPurchaseInline, PendingProductionInline, PendingSaleInline]
    readonly_fields = ('created_by', 'updated_by', 'created_at', 'updated_at')

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        # เช็คว่านี่คือการค้นหาจากระบบ Autocomplete หรือไม่
        if 'autocomplete' in request.path:
            referer = request.META.get('HTTP_REFERER', '')
            
            # ถ้าค้นหามาจากหน้า Purchase Order (ใบสั่งซื้อ)
            if 'purchaseorder' in referer:
                import re
                # แกะรหัส ID ของใบสั่งซื้อจาก URL (เช่น .../purchaseorder/3/change/)
                match = re.search(r'purchaseorder/(\d+)/change/', referer)
                if match:
                    po_id = match.group(1)
                    from .models import PurchaseOrder, Product
                    from django.db.models import Q
                    
                    try:
                        po = PurchaseOrder.objects.get(pk=po_id)
                        if po.supplier:
                            # 🎯 ล็อคทันที: เอาเฉพาะที่ Supplier นี้ขาย หรือรายการที่ไม่ใช่สินค้า
                            queryset = queryset.filter(
                                Q(product_suppliers__supplier=po.supplier) | Q(is_product=False)
                            )
                    except PurchaseOrder.DoesNotExist:
                        pass
        
        return queryset, use_distinct
    
    formfield_overrides = {
        models.ManyToManyField: {'widget': forms.CheckboxSelectMultiple},
    }

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        # ✅ ปรับ CSS ใหม่ ให้รองรับโครงสร้าง Checkbox ของเปรมครับ
        style = mark_safe("""
            <style>
                .field-tags .related-widget-wrapper,
                .field-tags ul,
                .field-tags div {
                    display: flex !important;
                    flex-direction: row !important;
                    flex-wrap: wrap !important;
                    gap: 10px !important;
                    align-items: center !important;
                }

                .field-tags ul li {
                    display: inline-block !important;
                    margin: 0 !important;
                    padding: 0 !important;
                }

                .field-tags label {
                    display: inline-flex !important;
                    flex-direction: row !important;
                    align-items: center !important;
                    background: #e9ecef !important;
                    border: 1px solid #ced4da !important;
                    border-radius: 20px !important;
                    padding: 4px 15px !important;
                    margin: 0 !important;
                    cursor: pointer;
                    white-space: nowrap !important; 
                }

                .field-tags input[type="checkbox"] {
                    margin: 0 8px 0 0 !important;
                    vertical-align: middle !important;
                }

                .field-tags ul li:before { content: none !important; }
                .field-tags br { display: none !important; } 
            </style>
        """)

        context['title'] = mark_safe(f"{context['title']} {style}")
        
        # อย่าลืมคำว่า return นะครับ เดี๋ยวพังแบบมะกี้
        return super().render_change_form(request, context, add, change, form_url, obj)

    # ✅ 3. ตัวโชว์ Tag ในหน้ารวมรายการสินค้า (โค้ดเปรมดีอยู่แล้วครับ)
    def display_tags(self, obj):
        tags = obj.tags.all()
        if not tags: return "-"
        html = "".join([
            f'<span style="background:{t.color}; color:white; padding:2px 8px; '
            f'border-radius:12px; margin-right:4px; font-size:11px; font-weight:bold; display:inline-block; margin-bottom:2px;">'
            f'{t.name}</span>' for t in tags
        ])
        return mark_safe(html)
    display_tags.short_description = "แท็ก"

    # 🛠️ จุดที่แก้เพื่อเลิกล่ม: ดัก Error การจัดรูปแบบตัวเลข
    def get_production_cost(self, obj):
        try:
            count = getattr(obj, 'bom_count', 0)
            avg_cost = getattr(obj, 'production_cost_avg', 0)

            # 🔥 ไม้ตาย: ล้างความเป็น SafeString ออกให้หมดก่อนแปลงเป็น float
            clean_str = str(avg_cost).replace(',', '').strip()
            # ถ้าเป็น HTML มา (มี <span...) ให้ตัดเอาเฉพาะตัวเลข
            if '<' in clean_str:
                import re
                clean_str = re.sub('<[^<]+?>', '', clean_str)
            
            try:
                price_val = float(clean_str)
            except:
                price_val = 0.0

            if count and count > 0:
                # จัดรูปแบบทศนิยมข้างนอก format_html เพื่อความปลอดภัย
                display_num = "{:,.2f}".format(price_val)
                return format_html('<b style="color: #28a745;">{}</b> <span style="color: #666;">({})</span>', display_num, count)
            
            if getattr(obj, 'has_bom', False):
                return format_html('<span style="color: #999;">0.00 (0)</span>')
        except Exception as e:
            return f"Err: {str(e)[:20]}"
        return "-"

    get_production_cost.short_description = "ต้นทุนผลิตเฉลี่ย (BOM)"

    def get_latest_barcode(self, obj):
        # ดึงจาก property ที่เราเขียนไว้ใน models
        return obj.latest_barcode
    get_latest_barcode.short_description = "บาร์โค้ด (ล่าสุด)"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(BOM)
class BOMAdmin(admin.ModelAdmin):
    list_display = ('name', 'product', 'total_cost_display', 'sale_price', 'unit', 'production_time', 'created_by')
    list_filter = ('product__category',)
    inlines = [BOMIngredientInline]
    readonly_fields = ('created_by', 'updated_by')

    def total_cost_display(self, obj):
        try:
            return f"{float(obj.total_cost):,.2f}"
        except: return "0.00"
    
    def save_model(self, request, obj, form, change):
        if not change: obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            kwargs["queryset"] = Product.objects.filter(has_bom=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('po_number', 'supplier', 'order_date', 'status', 'get_diff')
    list_filter = ('status', 'order_date', 'supplier')
    search_fields = ('po_number', 'invoice_no_supplier', 'supplier__company_name')
    inlines = [PurchaseItemInline, PurchaseReceiptLogInline]
    readonly_fields = ('created_by', 'status')

    actions = ['mark_as_completed']

    @admin.action(description="✅ เปลี่ยนสถานะเป็น: เสร็จงาน/ปิดงาน")
    def mark_as_completed(self, request, queryset):
        queryset.update(status='Completed')
        self.message_user(request, f"ปิดงานสำเร็จ {queryset.count()} รายการแล้วค่ะ")

    def response_change(self, request, obj):
        if "_complete_order" in request.POST:
            obj.status = 'Completed'
            obj.save()
            self.message_user(request, f"ปิดงานใบสั่งซื้อ {obj.po_number} เรียบร้อยแล้ว")
            return HttpResponseRedirect(".")
        return super().response_change(request, obj)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        script = mark_safe("""
            <script>
                django.jQuery(document).ready(function() {
                    var btn = '<input type="submit" value="เสร็จงาน (Complete)" name="_complete_order" style="background: #28a745; color: white; height: 35px; margin-right: 10px; border-radius: 4px; border: none; cursor: pointer; padding: 0 20px; font-weight: bold;">';
                    django.jQuery('.submit-row').prepend(btn);
                });
            </script>
        """)
        # ✅ เปลี่ยนจาก help_text มาเป็นฉีดที่ Title แทน ปุ่มจะขึ้นแน่นอน
        context['title'] = mark_safe(f"{context['title']} {script}")
        return super().render_change_form(request, context, add, change, form_url, obj)

    # ✅ แก้ไขตรงนี้: เพื่อให้บันทึก PurchaseReceiptLog ได้
    # ✅ ปรับโครงสร้างให้เหมือน SalesOrderAdmin เป๊ะๆ
    def save_formset(self, request, form, formset, change):
        if formset.model == PurchaseItem:
            # ส่วนของรายการสินค้า (Items) - ทำเหมือน SO
            instances = formset.save(commit=False)
            for instance in instances:
                instance.save()
            formset.save_m2m()
        else:
            # ✅ ส่วนของประวัติการรับของ (ReceiptLog) 
            # ใช้ท่าเดียวกับ SO คือ formset.save()
            # Django จะจัดการเรื่อง "ลบรายการที่ถูกติ๊ก Delete" ให้เอง 100% ครับ
            formset.save()

    # (ฟังก์ชันอื่นคงเดิมได้เลยค่ะ)
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_diff(self, obj):
        ordered = sum(i.quantity_ordered for i in obj.items.all())
        received = sum(l.quantity_received for l in obj.receipt_logs.all())
        return color_diff(received - ordered)
    
@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ('so_number', 'customer', 'order_date', 'status', 'vat_percent','get_diff')
    list_filter = ('status', 'order_date', 'customer')
    search_fields = ('so_number', 'po_no_customer', 'customer__company_name', 
        'items__product__barcodes__code')
    inlines = [SalesItemInline, SalesDeliveryLogInline]
    readonly_fields = ('created_by', 'status') # ล็อค status ให้ระบบจัดการออโต้
    
    actions = ['mark_as_completed']

    @admin.action(description="✅ เปลี่ยนสถานะเป็น: เสร็จงาน/ปิดงาน")
    def mark_as_completed(self, request, queryset):
        queryset.update(status='Completed')
        self.message_user(request, f"ปิดงานสำเร็จ {queryset.count()} รายการแล้วค่ะ")

    def response_change(self, request, obj):
        if "_complete_order" in request.POST:
            obj.status = 'Completed'
            obj.save()
            self.message_user(request, f"ปิดงานใบสั่งขาย {obj.so_number} เรียบร้อยแล้ว")
            return HttpResponseRedirect(".")
        return super().response_change(request, obj)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        script = mark_safe("""
            <script>
                django.jQuery(document).ready(function() {
                    var btn = '<input type="submit" value="เสร็จงาน (Complete)" name="_complete_order" style="background: #218838; color: white; height: 35px; margin-right: 10px; border-radius: 4px; border: none; cursor: pointer; padding: 0 20px; font-weight: bold;">';
                    django.jQuery('.submit-row').prepend(btn);
                });
            </script>
        """)
        context['title'] = mark_safe(f"{context['title']} {script}")
        return super().render_change_form(request, context, add, change, form_url, obj)
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_diff(self, obj):
        ordered = sum(i.quantity_ordered for i in obj.items.all())
        shipped = sum(l.quantity_shipped for l in obj.delivery_logs.all())
        return color_diff(shipped - ordered)
    get_diff.short_description = "สถานะส่งของ"

    # ❗ ต้องเพิ่มฟังก์ชันนี้เข้าไปด้วย ระบบถึงจะหาตัวสร้างใบ PD เจอครับ
    def create_auto_production_order(self, sales_item, user):
        import datetime
        from .models import ProductionOrder
        today_str = datetime.date.today().strftime('%Y%m%d')
        count = ProductionOrder.objects.filter(pd_number__contains=today_str).count() + 1
        pd_no = f"PD-{today_str}-{count:03d}"

        return ProductionOrder.objects.create(
            pd_number=pd_no,
            product=sales_item.product,
            quantity_planned=sales_item.quantity_ordered,
            status='Draft',
            order_date=datetime.date.today(),
            created_by=user,
            notes=f"สร้างอัตโนมัติจาก SO: {sales_item.sales_order.so_number}"
        )
    
    # ✅ ฟังก์ชันสร้างใบผลิตอัตโนมัติ
    def save_formset(self, request, form, formset, change):
        created_count = 0

        if formset.model == SalesItem:
            instances = formset.save(commit=False)
            created_count = 0
            for instance in instances:
                if isinstance(instance, SalesItem):
                    instance.sales_order = formset.instance 
                    if hasattr(instance, 'user'): instance.user = request.user
                    instance.save()
                    
                    if instance.auto_produce and instance.product.has_bom and not instance.is_produced:
                        self.create_auto_production_order(instance, request.user)
                        instance.is_produced = True 
                        instance.save()
                        created_count += 1
            formset.save_m2m()
            
            messages.success(request, f"ระบบสร้างใบผลิตอัตโนมัติสำเร็จ {created_count} รายการ")
        else:
            # ✅ บรรทัดนี้สำคัญมาก! ถ้าไม่ใช่ SalesItem (เช่นเป็น DeliveryLog) ให้เซฟปกติ
            formset.save()

        if created_count > 0:
            messages.success(request, f"ระบบได้สร้างใบผลิต (PD) ให้โดยอัตโนมัติจำนวน {created_count} รายการแล้วค่ะ")


@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = ('pd_number', 'product', 'quantity_planned', 'quantity_actual', 'get_diff', 'status')
    list_filter = ('status', 'order_date', 'product')
    search_fields = ('pd_number', 'product__name')
    inlines = [ProductionLogInline]
    readonly_fields = ('created_by', 'status') 
    
    actions = ['mark_as_completed']

    # ✅ ต้องมีฟังก์ชันนี้ และ Indent (ย่อหน้า) ให้ตรงกับฟังก์ชันอื่นในคลาสครับ
    @admin.action(description="✅ เปลี่ยนสถานะเป็น: เสร็จงาน/ปิดงาน")
    def mark_as_completed(self, request, queryset):
        queryset.update(status='Completed')
        self.message_user(request, f"ปิดงานผลิตสำเร็จ {queryset.count()} รายการแล้วค่ะ")

    def response_change(self, request, obj):
        if "_complete_order" in request.POST:
            obj.status = 'Completed'
            obj.save()
            self.message_user(request, f"ปิดงานผลิต {obj.pd_number} เรียบร้อยแล้ว")
            return HttpResponseRedirect(".")
        return super().response_change(request, obj)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        script = mark_safe("""
            <script>
                django.jQuery(document).ready(function() {
                    var btn = '<input type="submit" value="ปิดงานผลิต (Complete)" name="_complete_order" style="background: #28a745; color: white; height: 35px; margin-right: 10px; border-radius: 4px; border: none; cursor: pointer; padding: 0 20px; font-weight: bold;">';
                    django.jQuery('.submit-row').prepend(btn);
                });
            </script>
        """)
        context['title'] = mark_safe(f"{context['title']} {script}")
        return super().render_change_form(request, context, add, change, form_url, obj)


    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_diff(self, obj):
        planned = obj.quantity_planned
        actual = obj.quantity_actual
        return color_diff(actual - planned)
    get_diff.short_description = "สถานะผลิต"

    def save_formset(self, request, form, formset, change):
        if formset.model == ProductionLog:
            # ✅ 1. จัดการเรื่องลบ (เพื่อให้ลบประวัติผลิตแล้วยอดสต็อก/สถานะเด้งคืน)
            if hasattr(formset, 'deleted_objects'):
                for obj in formset.deleted_objects:
                    obj.delete()

            # ✅ 2. จัดการบันทึกยอดผลิตใหม่/แก้ไข
            instances = formset.save(commit=False)
            for instance in instances:
                if hasattr(instance, 'user') and not instance.user_id:
                    instance.user = request.user
                instance.save()
            formset.save_m2m()

            # ✅ 3. ไม้ตายแก้บัคสถานะ: คำนวณยอดผลิตจริงใหม่จาก Log ทั้งหมด
            # วิธีนี้จะทำให้ quantity_actual อัปเดตล่าสุดเสมอ สถานะถึงจะเปลี่ยนค่ะ
            from django.db.models import Sum
            obj = formset.instance
            total_finished = obj.production_logs.aggregate(Sum('quantity_finished'))['quantity_finished__sum'] or 0
            
            # อัปเดตยอดจริงเข้าที่ตัวใบผลิตหลัก
            obj.quantity_actual = total_finished
            obj.save() # สั่ง Save ตรงนี้ สถานะใน models.py จะถูกคำนวณใหม่ทันที
        else:
            formset.save()
            
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            kwargs["queryset"] = Product.objects.filter(has_bom=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class BuyPriceRangeFilter(admin.SimpleListFilter):
    title = 'ช่วงราคาทุน'
    parameter_name = 'price_range'

    def lookups(self, request, model_admin):
        return [
            ('0-100', '0 - 100 บาท'),
            ('101-500', '101 - 500 บาท'),
            ('501-1000', '501 - 1,000 บาท'),
            ('1001-plus', 'มากกว่า 1,000 บาท'),
        ]

    def queryset(self, request, queryset):
        if self.value() == '0-100': return queryset.filter(buy_price__lte=100)
        if self.value() == '101-500': return queryset.filter(buy_price__gt=100, buy_price__lte=500)
        if self.value() == '501-1000': return queryset.filter(buy_price__gt=500, buy_price__lte=1000)
        if self.value() == '1001-plus': return queryset.filter(buy_price__gt=1000)
        return queryset

@admin.register(StockPlanning)
class StockPlanningAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'stock_quantity', 'get_pending_in', 'get_pending_out', 'get_pending_prod', 'get_available', 'buy_price')
    list_filter = ('category', 'suppliers', ProductOnlyFilter, BuyPriceRangeFilter)
    search_fields = ('name', 'barcode__code')

    # 1. แก้ไขแผนรับ (PO): รวมสถานะ Draft และรายการที่ยังได้รับไม่ครบ
    def get_pending_in(self, obj):
        # รวมสถานะ Draft เข้าไปด้วย เพื่อให้เห็นยอดที่จะเข้าในอนาคต
        items = obj.purchaseitem_set.filter(
            purchase_order__status__in=['Draft', 'Confirmed', 'Received']
        )
        # คำนวณส่วนต่าง: ถ้าสั่ง 10 รับแล้ว 0 ก็ต้องโชว์ 10 (ค้างรับ)
        total = sum((i.quantity_ordered - i.quantity_received) for i in items)
        return total if total > 0 else 0
    get_pending_in.short_description = "แผนรับ (PO)"

    # 2. แก้ไขแผนส่ง (SO): รวมสถานะ Draft และรายการที่ยังส่งไม่ครบ (แม้ยังไม่เคยส่งเลยก็ตาม)
    def get_pending_out(self, obj):
        # รวมสถานะ Draft และรายการที่กุมยอดจองไว้
        items = obj.salesitem_set.filter(
            sales_order__status__in=['Draft', 'Confirmed', 'Shipped']
        )
        # คำนวณส่วนต่าง: ถ้าสั่ง 5 ส่งแล้ว 0 ก็ต้องโชว์ 5 (ค้างส่ง)
        total = sum((i.quantity_ordered - i.quantity_shipped) for i in items)
        return total if total > 0 else 0
    get_pending_out.short_description = "แผนส่ง (SO)"

    # 3. แก้ไขแผนผลิต (PD): ให้ครอบคลุมทุกสถานะที่ยังผลิตไม่เสร็จ
    def get_pending_prod(self, obj):
        orders = obj.productionorder_set.filter(
            status__in=['Draft', 'Started', 'Finished']
        )
        total = sum((o.quantity_planned - o.quantity_actual) for o in orders)
        return total if total > 0 else 0
    get_pending_prod.short_description = "แผนผลิต (PD)"

    # ... (get_available และส่วนอื่นๆ เหมือนเดิม) ...

    def get_available(self, obj):
        on_hand = obj.stock_quantity
        p_in = self.get_pending_in(obj)
        p_out = self.get_pending_out(obj)
        p_prod = self.get_pending_prod(obj)
        total = on_hand + p_in - p_out + p_prod
        color = "red" if total < 0 else "blue"
        return format_html('<b style="color: {};">{}</b>', color, total)
    get_available.short_description = "พร้อมขาย (Available)"

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    inlines = [ProductInCategoryInline]

    def changelist_view(self, request, extra_context=None):
        from django.db.models import Count
        # ✅ รวมร่าง: ดึง Tag พร้อมนับจำนวนสินค้า เรียงจากใช้บ่อยสุด (-num_products) และใหม่สุด (-id)
        tags = ProductTag.objects.annotate(num_products=Count('products')).order_by('-num_products', '-id')
        
        # ส่วนหัวของกล่อง Tag Cloud
        tag_html = '<div style="margin-bottom: 20px; padding: 20px; background: #fff; border: 1px solid #ddd; border-radius: 10px; line-height: 2.5; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">'
        tag_html += '<h3 style="margin:0 0 15px 0; color:#333; font-size:18px; border-bottom: 2px solid #eee; padding-bottom: 10px;">🏷️ แท็กยอดนิยม & แท็กมาใหม่ (คลิกเพื่อดูสินค้า)</h3>'
        
        if tags.exists():
            for tag in tags:
                count = tag.num_products
                # ✅ คำนวณขนาด Font: ยิ่งใช้เยอะ ยิ่งตัวใหญ่ (Max 24px, Min 13px)
                # min(count, 10) เพื่อไม่ให้ตัวใหญ่เกินไปจนล้นจอ
                font_size = 13 + (min(count, 10) * 1.1) 
                
                # ลิงก์ไปหน้ารายการสินค้าแบบ Filter Tag ID ทันที
                url = f"/admin/stocks/product/?tags__id__exact={tag.id}"
                
                tag_html += f'''
                    <a href="{url}" style="display: inline-block; margin: 5px 10px; padding: 5px 18px; 
                    background: {tag.color}; color: white; border-radius: 25px; text-decoration: none; 
                    font-weight: bold; font-size: {font_size}px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); 
                    transition: transform 0.2s; border: 1px solid rgba(0,0,0,0.1);">
                    #{tag.name} <span style="font-size: 11px; opacity: 0.85;">({count})</span>
                    </a>'''
        else:
            tag_html += '<p style="color:#999; padding: 10px;">ยังไม่มีการสร้างแท็กสินค้าในระบบ</p>'
        
        tag_html += '</div>'
        
        # ส่งค่าไปยัง Template ของ Django Admin
        extra_context = extra_context or {}
        extra_context['tag_cloud'] = mark_safe(tag_html)
        return super().changelist_view(request, extra_context=extra_context)

# ---------------------------------------------------------
# Register ProductTag เพื่อให้เมนูโผล่ในหน้า Admin
# ---------------------------------------------------------
@admin.register(ProductTag)
class ProductTagAdmin(admin.ModelAdmin):
    # แสดงชื่อแท็กและตัวอย่างสีในหน้า List
    list_display = ('display_name_with_count', 'color')
    search_fields = ('name',)
    # ✅ เพิ่ม Inline เข้าไปที่นี่ค่ะ
    inlines = [ProductInTagInline]

    def get_queryset(self, request):
        # ใช้ annotate นับจำนวนสินค้าที่เชื่อมกับ Tag นี้
        qs = super().get_queryset(request)
        return qs.annotate(product_count=models.Count('products'))

    def display_name_with_count(self, obj):
        # เอาชื่อ Tag มาต่อด้วยจำนวนสินค้า
        return f"{obj.name} ({obj.product_count})"
    display_name_with_count.short_description = "ชื่อแท็ก (จำนวนสินค้า)"

    def color_display(self, obj):
        # แสดงเป็นกล่องสีสวยๆ ให้เห็นในหน้า Admin เลยครับ
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 12px; font-weight: bold;">{}</span>',
            obj.color, obj.name
        )
    color_display.short_description = "ตัวอย่างสี"

    # ✅ แถม: เพิ่มฟังก์ชันนับจำนวนสินค้าในหน้า List ให้ดูง่ายๆ ค่ะ
    def get_product_count(self, obj):
        return obj.product_set.count()
    get_product_count.short_description = "จำนวนสินค้าที่ใช้"

class PaymentDateForm(forms.Form):
    payment_date = forms.DateField(
        label="ระบุวันที่ชำระเงิน",
        initial=datetime.date.today,
        widget=AdminDateWidget()
    )

@admin.action(description="🎯 ปิดยอด: กรณีพิเศษ/รับไม่ครบ (SETTLED)")    
def settle_income_special(modeladmin, request, queryset):
    if 'apply' in request.POST:
        # ตัดจบสถานะอย่างเดียว ไม่สร้างบันทึกการเงินเพิ่ม
        count = queryset.update(status='COMPLETED', payment_status='SETTLED')
        modeladmin.message_user(request, f"ตัดจบรายการรายรับสำเร็จ {count} รายการ (SETTLED)", messages.SUCCESS)
        return None

    return TemplateResponse(request, "admin/settle_confirmation.html", {
        **modeladmin.admin_site.each_context(request),
        'title': "ยืนยันปิดยอดรายรับกรณีพิเศษ (SETTLED)",
        'queryset': queryset,
        'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        'action_name': 'settle_income_special', # ต้องตรงกับชื่อฟังก์ชัน,
        'mode': 'income'
    })
settle_income_special.short_description = "🎯 ปิดยอดกรณีพิเศษ (SETTLED)"

# ✅ ปุ่มใหม่สำหรับฝั่งรายจ่าย (Purchase)
def settle_purchase_special(modeladmin, request, queryset):
    if 'apply' in request.POST:
        count = queryset.update(status='COMPLETED', payment_status='SETTLED')
        modeladmin.message_user(request, f"ตัดจบรายการรายจ่ายสำเร็จ {count} รายการ (SETTLED)", messages.SUCCESS)
        return None

    return TemplateResponse(request, "admin/settle_confirmation.html", {
        **modeladmin.admin_site.each_context(request),
        'title': "ยืนยันปิดยอดรายจ่ายกรณีพิเศษ (SETTLED)",
        'queryset': queryset,
        'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        'action_name': 'settle_purchase_special'
    })
settle_purchase_special.short_description = "🎯 ปิดยอดกรณีพิเศษ (SETTLED)"

# ✅ Action: ปิดงาน Finance แบบมีหน้ายืนยัน (Confirmation Page)
@admin.action(description='💰 ชำระครบ/ปิดยอด (Settle Payment)')
def settle_and_close_orders(modeladmin, request, queryset):
    # ... (Logic ปิดงาน) ...
    if 'apply' in request.POST:
        form = PaymentDateForm(request.POST)
        if form.is_valid():
            pay_date = form.cleaned_data['payment_date']
            updated_count = 0
            
            for obj in queryset:
                balance = obj.balance_due
                # สร้างรายการจ่ายเงิน (ตามยอดที่ค้าง)
                if balance > 0:
                    if isinstance(obj, PurchaseOrder):
                        PurchasePaymentLog.objects.create(purchase_order=obj, amount=balance, payment_date=pay_date, notes="Auto Settle")
                        obj.refresh_from_db()
                    elif isinstance(obj, SalesOrder): # รองรับทั้ง SalesOrder และ IncomeReport
                        SalesPayment.objects.create(order=obj, amount=balance, payment_date=pay_date, remark="Auto Settle")
                        obj.refresh_from_db()
                    updated_count += 1
                
                # บังคับอัปเดตสถานะการเงินเป็น "Paid"
                if obj.balance_due <= 0:
                    obj.payment_status = 'Paid'
                else:
                    obj.payment_status = 'Partial' # เพิ่มบรรทัดนี้เผื่อปิดยอดไม่หมดค่ะ
                
                obj.save(update_fields=['payment_status'])
            
            modeladmin.message_user(request, f"✅ บันทึกการชำระเงินเรียบร้อย {updated_count} รายการ", messages.SUCCESS)
            return HttpResponseRedirect(request.get_full_path())
            
    else:
        form = PaymentDateForm()

    # HTML Template สำหรับหน้าเลือกวันที่
    html_template = """
    {% extends "admin/base_site.html" %}
    {% load i18n admin_urls static admin_modify %}
    {% block extrahead %}{{ block.super }}<script src="{% url 'admin:jsi18n' %}"></script>{{ media }}{% endblock %}
    {% block content %}
    <div style="max-width: 600px; margin: 20px auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <h2 style="color: #007bff;">💰 ยืนยันการชำระเงินและปิดยอด ({{ queryset.count }} รายการ)</h2>
        <p>ระบบจะสร้างรายการชำระเงิน <b>"เต็มจำนวนคงเหลือ"</b> และเปลี่ยนสถานะเป็น <b>Paid</b> ให้อัตโนมัติ</p>
        <form method="post">{% csrf_token %}
            {% for obj in queryset %}<input type="hidden" name="{{ action_checkbox_name }}" value="{{ obj.pk }}">{% endfor %}
            <input type="hidden" name="action" value="settle_and_close_orders">
            <input type="hidden" name="apply" value="1">
            <div style="margin: 20px 0;">{{ form.as_p }}</div>
            <button type="submit" style="background: #007bff; color: white; border: none; padding: 10px 20px; font-size: 16px; border-radius: 4px; cursor: pointer;">✅ ยืนยัน (Confirm)</button>
            <a href="#" onclick="window.history.back();" style="margin-left: 10px; color: #666;">ยกเลิก</a>
        </form>
    </div>
    {% endblock %}
    """
    
    context = {
        'queryset': queryset, 'form': form, 'media': form.media, 
        'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME, 'opts': modeladmin.model._meta,
    }
    return HttpResponse(Template(html_template).render(RequestContext(request, context)))

@admin.register(FinanceReport)
class FinanceReportAdmin(admin.ModelAdmin):
    # หน้ารวม: ดูง่ายๆ ว่าใบไหนค้างจ่าย
    search_fields = ('po_number', 'supplier__company_name')
    actions = [settle_and_close_orders, settle_purchase_special]

    # จัดหน้าตาฟอร์ม
    # ✅ 1. เปลี่ยน list_display ให้โชว์ Payment Status แทน
    list_display = ('po_number', 'supplier', 'get_grand_total_list', 'get_balance_due_list', 'payment_status')
    
    # ✅ 2. ตัวกรอง ก็ต้องกรองตามการจ่ายเงิน
    list_filter = ('payment_status', 'supplier') 

    # ✅ 3. ในหน้า Detail ก็เปลี่ยน fields
    fieldsets = (
        ('📊 สรุปยอดเงิน', {
            'fields': (
                ('get_total_items_display', 'get_subtotal_display'), 
                ('vat_percent', 'get_vat_amount_display'), 
                ('get_grand_total_display', 'get_total_paid_display', 'get_balance_due_display')
            ),
            'classes': ('wide',), 
        }),
        ('📝 ข้อมูลเอกสาร', {
            # โชว์ทั้ง 2 สถานะเลยก็ได้ครับ บัญชีจะได้รู้ว่า ของมาครบหรือยัง
            'fields': ('po_number', 'supplier', 'order_date', 'status', 'payment_status')
        }),
    )

    readonly_fields = (
        'po_number', 'supplier', 'order_date', 
        'get_total_items_display', 'get_subtotal_display', 
        'get_vat_amount_display', 'get_grand_total_display', 
        'get_total_paid_display', 'get_balance_due_display',
        'status', 'payment_status' # <-- ห้ามแก้สถานะมือ ให้ระบบคำนวณเอง
    )

    inlines = [PurchaseItemReadOnlyInline, PurchasePaymentInline]

    # --- ส่วนที่แก้ไข: ใช้ f-string จัดตัวเลขก่อนส่งไป format_html ทุกตัว ---
        # บันทึก User คนจ่ายเงินอัตโนมัติ
    def save_formset(self, request, form, formset, change):
        # 1. บันทึกข้อมูลที่กรอกในตารางก่อน
        formset.save()
    
        # 2. ดึงใบสั่งซื้อใบนี้ออกมา
        obj = formset.instance
    
        # 3. เช็คว่าถ้าเป็นการเซฟตาราง "บันทึกการจ่ายเงิน" ให้คำนวณสถานะใหม่
        if formset.model == PurchasePaymentLog:
            from django.db.models import Sum
        
        # ✅ ท่าไม้ตาย: ไม่ต้องง้อ _set แต่สั่งไปที่ Model PurchasePaymentLog โดยตรงเลย
        # กรองเอาเฉพาะรายการที่ฟิลด์ 'order' ตรงกับใบนี้
            paid_data = PurchasePaymentLog.objects.filter(purchase_order=obj).aggregate(Sum('amount'))
            paid = paid_data['amount__sum'] or 0
        
            # ยอดสุทธิที่ต้องจ่าย
            total = obj.grand_total

            # 🟢 เปลี่ยนสถานะตาม Choice ที่เปรมมีใน Model
            if paid <= 0:
                obj.payment_status = 'Unpaid'
            elif paid < total:
                obj.payment_status = 'Partial'  # 🟠 นี่คือ "จ่ายบางส่วน" ที่เปรมต้องการ!
            else:
                obj.payment_status = 'Paid'     # 🟢 จ่ายครบแล้ว
            
            # บันทึกสถานะลงฐานข้อมูล
            obj.save(update_fields=['payment_status'])
    
    def get_total_items_display(self, obj):
        return f"{sum(i.quantity_ordered for i in obj.items.all()):,}"
    get_total_items_display.short_description = "📦 รวมจำนวนสินค้า"

    def get_subtotal_display(self, obj):
        # ✅ แก้ไข: จัดรูปแบบตัวเลขก่อนส่งเข้า HTML
        return format_html('<span style="font-size:14px;">{}</span>', f"{obj.total_items_price:,.2f}")
    get_subtotal_display.short_description = "💵 ราคารวม (ก่อน VAT)"

    def get_vat_amount_display(self, obj):
        return f"{obj.vat_amount:,.2f}"
    get_vat_amount_display.short_description = "ภาษีมูลค่าเพิ่ม (VAT)"

    def get_grand_total_display(self, obj):
        # ✅ แก้ไข: จัดรูปแบบตัวเลขก่อนส่งเข้า HTML
        return format_html('<b style="color:#007bff;">{}</b>', f"{obj.grand_total:,.2f}")
    get_grand_total_display.short_description = "💰 ยอดสุทธิ (Grand Total)"

    def get_total_paid_display(self, obj):
        # ✅ แก้ไข
        return format_html('<b style="color:#28a745;">{}</b>', f"{obj.total_paid:,.2f}")
    get_total_paid_display.short_description = "✅ จ่ายแล้ว"

    def get_balance_due_display(self, obj):
        # ✅ แก้ไข
        balance = obj.balance_due
        color = "red" if balance > 0 else "green"
        text = f"{balance:,.2f}"
        return format_html('<b style="color:{};">{}</b>', color, text)
    get_balance_due_display.short_description = "❗️ ยอดค้างจ่าย"

    # --- List Display Functions (หน้ารวม) ---
    def get_grand_total_list(self, obj): 
        return f"{obj.grand_total:,.2f}"
    get_grand_total_list.short_description = "ยอดสุทธิ"

    def get_balance_due_list(self, obj):
        # 1. คำนวณหา Grand Total ที่แท้จริง (รวม VAT แล้ว)
        subtotal = getattr(obj, 'total_items_price', 0) or 0
        vat_p = getattr(obj, 'vat_percent', 0) or 0
        grand_total = subtotal + (subtotal * vat_p / 100)
        # 2. หักยอดที่จ่ายมาแล้ว
        paid = getattr(obj, 'total_paid', 0) or 0
        bal = grand_total - paid
        # 3. Logic การโชว์สีแบบเดิมที่เปรมต้องการ
        if bal <= 0: 
            # ถ้าจ่ายครบหรือจ่ายเกิน ให้โชว์ 0.00 สีเขียว
            return format_html('<span style="color:green; font-weight:bold;">{}</span>', "0.00")
        # ถ้ายังค้างชำระ ให้โชว์ยอดค้างเป็นสีแดง (ติดลบตามสไตล์เปรม)
        return format_html('<span style="color:red; font-weight:bold;">-{}</span>', f"{bal:,.2f}")

# 2. หน้า Admin ของ Income Report
@admin.register(IncomeReport)
class IncomeReportAdmin(admin.ModelAdmin):
    # ✅ ปรับ list_display ให้เอาตัวที่มีสีมาโชว์เลย จะได้ดูง่ายๆ
    list_display = ('so_number', 'customer', 'get_grand_total_display', 'get_balance_due_display', 'payment_status')
    list_filter = ('payment_status', 'status', 'customer', 'order_date')
    search_fields = ('so_number', 'customer__company_name')
    actions = [settle_and_close_orders, settle_income_special]

    fieldsets = (
        ('📊 สรุปยอดเงิน (Income Summary)', {
            'fields': (
                ('get_total_items_display', 'get_subtotal_display'), 
                ('get_vat_percent_display','get_vat_amount_display'), 
                ('get_grand_total_display', 'get_total_paid_display', 'get_balance_due_display')
            ),
        }),
        ('📝 ข้อมูลเอกสาร', {
            'fields': ('so_number', 'customer', 'order_date', 'status', 'payment_status')
        }),
    )

    readonly_fields = (
        'so_number', 'customer', 'order_date', 'status', 'payment_status',
        'get_total_items_display', 'get_subtotal_display', 'get_vat_percent_display',
        'get_vat_amount_display', 'get_grand_total_display', 
        'get_total_paid_display', 'get_balance_due_display'
    )

    inlines = [SalesItemReadOnlyInline, SalesPaymentInline]

    # --- Methods ที่ปรับปรุงใหม่ (ใช้ได้ทั้ง List และ Detail) ---
    def save_formset(self, request, form, formset, change):
        # 1. เซฟรายการรับเงิน
        formset.save()
        
        # 2. คำนวณสถานะ
        obj = formset.instance
        # ฝั่งขายใช้ SalesPayment (เปรมต้องเช็ค related_name ใน model นะคะ)
        # ถ้าไม่มีใช้ salespayment_set
        paid = sum(p.amount for p in obj.payments.all())
        total = obj.grand_total
        
        if paid <= 0:
            obj.payment_status = 'Unpaid'
        elif paid < total:
            obj.payment_status = 'Partial' # จ่ายบางส่วน
        else:
            obj.payment_status = 'Paid'
            
        obj.save(update_fields=['payment_status'])

    def get_total_items_display(self, obj):
        # ใช้ Sum จาก django.db.models (ซึ่งในไฟล์ admin ของเปรมยังไม่ได้ import ไว้ด้านบน)
        from django.db.models import Sum
        
        # ดึงจาก related_name='items' ที่ตั้งไว้ใน SalesItem
        result = obj.items.aggregate(total_qty=Sum('quantity_ordered'))
        total = result['total_qty'] or 0
        
        if total > 0:
            return f"{total:,} ชิ้น"
        return "0 ชิ้น"
    
    # ✅ จุดที่ 3: ชื่อตรงนี้ก็ต้องตรงกัน
    get_total_items_display.short_description = "📦 รวมจำนวนสินค้า"

    def get_subtotal_display(self, obj):
        # ✅ จัดรูปแบบด้วย f-string ให้เสร็จก่อน แล้วค่อยส่งเข้า format_html
        value = f"{obj.total_items_price:,.2f}"
        return format_html('<span style="font-size:14px;">{}</span>', value)
    get_subtotal_display.short_description = "💵 ก่อน VAT"

    # 1. ฟังก์ชันดึง % VAT มาโชว์ (อ่านอย่างเดียว)
    def get_vat_percent_display(self, obj):
        return f"{obj.vat_percent}%"
    get_vat_percent_display.short_description = "อัตราภาษี (%)"

    # 2. ฟังก์ชันคำนวณยอดเงิน VAT (ดึงค่าจากแม่มาคำนวณ)
    def get_vat_amount_display(self, obj):
        # คำนวณ: (ราคาก่อน VAT * % VAT) / 100
        subtotal = getattr(obj, 'total_items_price', 0) # สมมติว่าเปรมมี property นี้ใน SalesOrder
        vat_p = obj.vat_percent or 0
        vat_amt = (subtotal * vat_p) / 100
        return f"{vat_amt:,.2f}"
    get_vat_amount_display.short_description = "ภาษีมูลค่าเพิ่ม (VAT)"

    def get_grand_total_display(self, obj):
        subtotal = getattr(obj, 'total_items_price', 0)
        vat_p = obj.vat_percent or 0
        total = subtotal + ((subtotal * vat_p) / 100)
        formatted_total = f"{total:,.2f}"
        return format_html('<b style="color:#007bff;">{}</b>', formatted_total)
    get_grand_total_display.short_description = "💰 ยอดสุทธิ (Grand Total)"

    def get_total_paid_display(self, obj):
        value = f"{obj.total_paid:,.2f}"
        return format_html('<b style="color:#28a745;">{}</b>', value)
    get_total_paid_display.short_description = "✅ รับแล้ว"

    def calculate_balance_due(self, obj):
        subtotal = getattr(obj, 'total_items_price', 0) or 0
        vat_p = getattr(obj, 'vat_percent', 0) or 0
        # ยอดรวมภาษี
        grand_total = subtotal + (subtotal * vat_p / 100)
        # หักยอดที่รับเงินมาแล้ว
        paid = getattr(obj, 'total_paid', 0) or 0
        return grand_total - paid

    # สำหรับโชว์ในหน้าตาราง (List View)
    def get_balance_due_list(self, obj):
        bal = self.calculate_balance_due(obj)
        if bal <= 0:
            return format_html('<span style="color:green; font-weight:bold;">0.00</span>')
        return format_html('<span style="color:red; font-weight:bold;">-{}</span>', f"{bal:,.2f}")
    get_balance_due_list.short_description = "ยอดคงค้าง"

    # สำหรับโชว์ในหน้าแก้ไข (Detail View / Fieldsets)
    def get_balance_due_display(self, obj):
        bal = self.calculate_balance_due(obj)
        color = "green" if bal <= 0 else "red"
        return format_html('<b style="color:{}; font-size:1.1em;">{}</b>', color, f"{max(0, bal):,.2f}")
    get_balance_due_display.short_description = "ยอดเงินคงค้าง (Balance Due)"

@admin.register(ShipmentPaymentReport)
class ShipmentPaymentReportAdmin(admin.ModelAdmin):
    # ✅ โชว์มูลค่าที่ส่ง และวันที่จะได้รับเงินของยอดนั้นๆ
    list_display = ['payment_due_date', 'get_so_number', 'get_customer', 'quantity_shipped', 'get_shipment_value_display', 'get_dc_display','get_rebate_display', 'get_total_with_vat_display']
    search_fields = ['sales_order__so_number', 'sales_order__customer__company_name']
    list_filter = ['payment_due_date', 'sales_order__customer']
    ordering = ['payment_due_date']

    def get_dc_display(self, obj):
        # โชว์ตัวเลขคลีนๆ มีคอมม่าและทศนิยม 2 ตำแหน่ง
        return f"{obj.dc_amount:,.2f}"
    get_dc_display.short_description = "หัก DC"
    get_dc_display.admin_order_field = 'dc_amount'

    def get_rebate_display(self, obj):
        # โชว์ตัวเลขคลีนๆ มีคอมม่าและทศนิยม 2 ตำแหน่ง
        return f"{obj.rebate_amount:,.2f}"
    get_rebate_display.short_description = "หัก Rebate"
    get_rebate_display.admin_order_field = 'rebate_amount'

    def get_so_number(self, obj):
        return obj.sales_order.so_number
    get_so_number.short_description = "เลขที่ SO"
    get_so_number.admin_order_field = 'sales_order__so_number' # ทำให้กดเรียงลำดับได้ด้วยค่ะ

    def get_customer(self, obj):
        # ดึงชื่อลูกค้าจาก SalesOrder -> Customer
        return obj.sales_order.customer.company_name
    get_customer.short_description = 'ลูกค้า' # ชื่อหัวตาราง
    get_customer.admin_order_field = 'sales_order__customer__company_name'

    def get_shipment_value_display(self, obj):
        return f"{obj.shipment_value:,.2f}"
    get_shipment_value_display.short_description = 'มูลค่าสินค้า (ก่อน VAT)'

    def get_total_with_vat_display(self, obj):
        # ดึงค่าจาก property ใน model มาโชว์
        return f"{obj.total_with_vat:,.2f}"
    get_total_with_vat_display.short_description = 'ยอดรวมสุทธิ (รวม VAT)'

    def has_add_permission(self, request):
        return False
    
@admin.register(CustomerProductContract)
class CustomerProductContractAdmin(admin.ModelAdmin):
    list_display = ['customer', 'product', 'contract_price', 'dc_percent', 'rebate_percent']
    list_editable = ['contract_price', 'dc_percent', 'rebate_percent'] # แก้ไขแบบรวดเร็วได้
    search_fields = ['customer__company_name', 'product__name', 'product__barcodes__code']
    autocomplete_fields = ['product']

@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'product', 'adjustment_type', 'quantity', 'adjustment_value', 'reason']
    list_filter = ['adjustment_type', 'product']
    autocomplete_fields = ['product']
    search_fields = ['product__name', 'reason']

admin.site.register(Customer)
