import json
from django.contrib import admin
from .models import ProductTag
from .models import *
from .models import DocumentLock
# 1. เปลี่ยนชื่อที่ปรากฏบนหัวเอกสาร (Header สีน้ำเงิน)
admin.site.site_header = "Meebun ERP"

# 2. เปลี่ยนชื่อที่ปรากฏบน Browser Tab (Title)
admin.site.site_title = "Meebun ERP Admin"

# 3. เปลี่ยนชื่อหัวข้อหลักในหน้าแรก (Index Title)
admin.site.index_title = "ยินดีต้อนรับสู่ระบบจัดการข้อมูล"
from django.contrib import messages

from django.contrib.admin.widgets import AdminDateWidget
from django.contrib.admin import helpers  # <--- helpers ต้องดึงมาจาก admin ครับ
from django.utils.html import format_html
from django.core.exceptions import ValidationError
from django.forms import TextInput
from django.db import models # เพิ่มเพื่อรองรับ formfield_overrides
from django.db.models import Subquery, OuterRef,Q, Sum, F, DecimalField, ExpressionWrapper
from django import forms # ✅ เพิ่มบรรทัดนี้ครับ ทำระบบ tag checkbox
from django.utils.safestring import mark_safe # ✅ ต้องมีบรรทัดนี้ครับ
# เพิ่มที่บรรทัดบนสุดของไฟล์ครับ
from django.http import HttpResponseRedirect
from django.template import Template, RequestContext 
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse # ✅ 3บรรทัดนี้ สำหรับระบบล็อคเอกสาร
from django.contrib.contenttypes.models import ContentType
from datetime import timedelta
from django.utils import timezone
from decimal import Decimal

# 📅 คลาสพิเศษสำหรับสร้างช่องเลือกวันที่ "เริ่มต้น - สิ้นสุด" เอง
class DateRangeFilter(admin.FieldListFilter):
    template = 'admin/date_range_filter.html' # ถ้าเปรมไม่มีไฟล์นี้ มันจะใช้ตัวสำรองให้ครับ

    def __init__(self, field, request, params, model, model_admin, field_path):
        super().__init__(field, request, params, model, model_admin, field_path)
        self.lookup_kwarg_gte = f'{field_path}__date__gte'
        self.lookup_kwarg_lte = f'{field_path}__date__lte'
        self.lookup_val_gte = params.get(self.lookup_kwarg_gte)
        self.lookup_val_lte = params.get(self.lookup_kwarg_lte)

    def expected_parameters(self):
        return [self.lookup_kwarg_gte, self.lookup_kwarg_lte]

    def choices(self, changelist):
        yield {
            'selected': self.lookup_val_gte is None and self.lookup_val_lte is None,
            'query_string': changelist.get_query_string(remove=[self.lookup_kwarg_gte, self.lookup_kwarg_lte]),
            'display': 'ทั้งหมด',
        }

class DocumentLockMixin:
    def change_view(self, request, object_id, form_url='', extra_context=None):
        content_type = ContentType.objects.get_for_model(self.model)
        
        # 1. เช็คว่ามีใครล็อกใบนี้อยู่ไหม
        lock = DocumentLock.objects.filter(content_type=content_type, object_id=object_id).first()
        
        if lock:
            # 2. ถ้ามีคนล็อกอยู่ และไม่ใช่เรา + ล็อกยังไม่หมดอายุ -> "ห้ามเข้า"
            if lock.user != request.user and not lock.is_expired():
                messages.error(
                    request, 
                    f"⛔ หยุดก่อน! ใบนี้กำลังถูกแก้ไขโดย {lock.user.get_full_name() or lock.user.username} "
                    f"กรุณารอประมาณ 10 นาที หรือติดต่อผู้ใช้คนดังกล่าวค่ะ"
                )
                # ดีดกลับไปหน้า List ทันที
                return HttpResponseRedirect(reverse(f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist'))
            
            # 3. ถ้าเป็นเราเอง หรือล็อกมันหมดอายุแล้ว -> "ต่ออายุล็อก"
            lock.user = request.user
            lock.save()
        else:
            # 4. ถ้ายังไม่มีใครล็อก -> "สร้างล็อกใหม่"
            DocumentLock.objects.create(content_type=content_type, object_id=object_id, user=request.user)
            
        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        # เมื่อกด Save เสร็จสมบูรณ์ -> "ปลดล็อก" ให้คนอื่นเข้าต่อได้ทันที
        super().save_model(request, obj, form, change)
        content_type = ContentType.objects.get_for_model(self.model)
        DocumentLock.objects.filter(content_type=content_type, object_id=obj.pk).delete()

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
    
class DatePeriodFilter(admin.SimpleListFilter):
    title = 'ช่วงเวลารายงาน'
    parameter_name = 'period'

    def lookups(self, request, model_admin):
        return (
            ('1year', 'ย้อนหลัง 1 ปี (Default)'),
            ('4months', 'ย้อนหลัง 4 เดือน'),
            ('1month', 'ย้อนหลัง 1 เดือน'),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == '1year':
            return queryset.filter(sales_items__sales_order__order_date__year=now.year)
        if self.value() == '4months':
            start_date = now - timedelta(days=120)
            return queryset.filter(sales_items__sales_order__order_date__gte=start_date)
        if self.value() == '1month':
            start_date = now - timedelta(days=30)
            return queryset.filter(sales_items__sales_order__order_date__gte=start_date)
        return queryset # Default จะไปจัดการใน get_queryset

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
    readonly_fields = ('get_status_from_logs',)

    def get_status_from_logs(self, obj):
        # 🎯 สายไฟเชื่อมข้อมูล: ไปดึงยอดที่ยืนยันแล้วจาก SalesDeliveryLog มาโชว์
        # ถ้าเปรมอยากให้ล็อคยอดอัตโนมัติ เราจะใช้ readonly_fields คลุมทับอีกทีครับ
        return "ยืนยันแล้วจากหน้า C6" if obj.sales_order.salesdeliverylog_set.filter(is_revenue_confirmed=True).exists() else "รอยืนยัน"
    get_status_from_logs.short_description = "สถานะรับเงิน"

    def has_change_permission(self, request, obj=None):
        # 🎯 ถ้าใบสั่งขายนี้มียอดที่คอนเฟิร์มใน C6 แล้ว ห้ามแก้หน้า C3
        if obj:
            from .models import SalesDeliveryLog # 👈 Import มาใช้ตรงๆ
            already_confirmed = SalesDeliveryLog.objects.filter(
                sales_order=obj, 
                is_revenue_confirmed=True
            ).exists()
            
            if already_confirmed:
                return False
        return True
    
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
            sales_order__status__in=['Completed', 'Cancelled']
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
    # 🎯 เก็บความสามารถเดิมไว้: ช่วยให้ค้นหาชื่อสินค้าได้ไวขึ้น
    autocomplete_fields = ['product'] 
    extra = 0
    
    # 🎯 จัดเรียงคอลัมน์ใหม่ตามที่เปรมต้องการ
    fields = [
        'product', 
        'quantity_ordered', 
        'quantity_received', 
        'get_pending',     # ✅ คอลัมน์ "ขาดรับ"
        'unit_price', 
        'total_price'      # ✅ คอลัมน์ "ราคารวม"
    ]
    
    # 🎯 ป้องกันการแก้เลขที่ระบบควรคำนวณเอง
    readonly_fields = ['quantity_received', 'get_pending', 'total_price']

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
    def get_pending(self, obj):
        # ตรวจสอบค่าว่างก่อนคำนวณป้องกัน Error
        qty_ordered = obj.quantity_ordered or 0
        qty_received = obj.quantity_received or 0
        
        diff = qty_ordered - qty_received
        
        if diff > 0:
            # ✅ แสดงยอดติดลบสีแดง (-X) สำหรับยอดที่ยังขาดรับ
            return format_html('<b style="color:#dc3545;">-{}</b>', diff)
        return 0
    
    get_pending.short_description = "ขาดรับ"

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
    readonly_fields = ('user',)
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'style': 'width: 120px;', 'placeholder': 'เลขใบส่งของ'})},
        models.TextField: {'widget': TextInput(attrs={'style': 'width: 200px;', 'placeholder': 'หมายเหตุ'})},
    }

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            resolved = request.resolver_match
            if resolved and 'object_id' in resolved.kwargs:
                so_id = resolved.kwargs['object_id']
                kwargs["queryset"] = Product.objects.filter(sales_items__sales_order_id=so_id).distinct()
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
class SupplierAdmin(DocumentLockMixin,admin.ModelAdmin):
    list_display = ('company_name', 'contact_person', 'type')
    inlines = [SupplierProductInline]

@admin.register(Product)
class ProductAdmin(DocumentLockMixin,admin.ModelAdmin):
    list_display = ('name', 'display_tags', 'get_latest_barcode', 'buy_price', 'get_production_cost', 'sale_price', 'stock_quantity', 'unit','get_total_stock_value', 'has_bom', 'created_by')
    list_filter = ('category','is_product', 'tags', 'has_bom', 'suppliers')
    search_fields = ('name', 'barcodes__code','tags__name')
    inlines = [ProductBarcodeInline, ProductSupplierInline,PendingPurchaseInline, PendingProductionInline, PendingSaleInline]
    readonly_fields = ('created_by', 'updated_by', 'created_at', 'updated_at')

    # ✅ ใช้ตัวนี้แทน filter_horizontal หรือ filter_vertical ค่ะ
    autocomplete_fields = ['tags']

    # --- ให้การค้นหา ใช้ รูปแบบ และ หรือ ได้ ---
    def get_search_results(self, request, queryset, search_term):
        # 🎯 1. จัดการระบบ OR (|) ก่อน
        if '|' in search_term:
            import operator
            from django.db.models import Q
            from functools import reduce
            parts = [p.strip() for p in search_term.split('|') if p.strip()]
            q_objects = []
            for part in parts:
                q_part = Q()
                for field in self.search_fields:
                    q_part |= Q(**{f"{field}__icontains": part})
                q_objects.append(q_part)
            queryset = queryset.filter(reduce(operator.or_, q_objects))
            use_distinct = False
        else:
            # ถ้าไม่มี | ให้ค้นหาปกติ
            queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        # 🎯 2. จัดการระบบ Autocomplete สำหรับ PO (ล็อคตาม Supplier)
        if 'autocomplete' in request.path:
            referer = request.META.get('HTTP_REFERER', '')
            if 'purchaseorder' in referer:
                import re
                match = re.search(r'purchaseorder/(\d+)/change/', referer)
                if match:
                    po_id = match.group(1)
                    from .models import PurchaseOrder
                    from django.db.models import Q
                    try:
                        po = PurchaseOrder.objects.get(pk=po_id)
                        if po.supplier:
                            queryset = queryset.filter(
                                Q(product_suppliers__supplier=po.supplier) | Q(is_product=False)
                            )
                    except PurchaseOrder.DoesNotExist: pass
        
        return queryset, use_distinct


    # 🎯 2. ปรับ CSS สำหรับแนวตั้งโดยเฉพาะ (เน้นความคลีน)
    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
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

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _total_stock_value=ExpressionWrapper(
                F('stock_quantity') * F('sale_price'),
                output_field=DecimalField()
            )
        )
        return queryset
    # 3. สร้างฟังก์ชันแสดงผล (ใน ProductAdmin)
    @admin.display(description='มูลค่า', ordering='-_total_stock_value')
    def get_total_stock_value(self, obj):
        # ✅ ใช้ int() เพื่อปัดเศษทศนิยมทิ้ง และใช้ :, เพื่อใส่คอมมาคั่นหลักพัน
        value = obj._total_stock_value or 0
        return f"{int(value):,}"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(BOM)
class BOMAdmin(DocumentLockMixin,admin.ModelAdmin):
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
class PurchaseOrderAdmin(DocumentLockMixin,admin.ModelAdmin):
    list_display = ('po_number', 'supplier', 'order_date', 'status', 'get_diff')
    list_filter = ('status', 'order_date', 'supplier')
    search_fields = ('po_number', 'invoice_no_supplier', 'items__product__name',
    'items__product__barcodes__code', 'supplier__company_name')
    inlines = [PurchaseItemInline, PurchaseReceiptLogInline]
    date_hierarchy = 'order_date' # ✅ เพิ่มบรรทัดนี้ค่ะ
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
class SalesOrderAdmin(DocumentLockMixin,admin.ModelAdmin):
    list_display = ('so_number', 'customer', 'order_date', 'status', 'vat_percent','get_diff')
    list_filter = ('status', 'order_date', 'customer')
    search_fields = ('so_number', 'po_no_customer', 'customer__company_name', 
        'items__product__barcodes__code')
    inlines = [SalesItemInline, SalesDeliveryLogInline, SalesPaymentInline]
    readonly_fields = ('created_by', 'status') # ล็อค status ให้ระบบจัดการออโต้
    date_hierarchy = 'order_date' # ✅ เพิ่มบรรทัดนี้ค่ะ
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
        """
        ฟังก์ชันช่วยสร้างใบผลิตอัตโนมัติจากรายการขาย
        """
        from .models import ProductionOrder, BOM
        
        # 🛑 1. เช็กเงื่อนไข BOM ก่อนสร้าง (Logic ป้องกัน Error)
        # ต้องมีการติ๊ก has_bom และต้องมีข้อมูลสูตรในระบบจริง
        has_bom_data = BOM.objects.filter(product=sales_item.product).exists()
        if not getattr(sales_item.product, 'has_bom', False) or not has_bom_data:
            return None # คืนค่า None เพื่อให้ตัว Action รู้ว่าตัวนี้สร้างไม่ได้

        # ✅ 2. สร้างใบผลิต (ปล่อยให้ model.save() รันเลข PD เอง)
        return ProductionOrder.objects.create(
            product=sales_item.product,
            quantity_planned=sales_item.quantity, # ใช้ชื่อฟิลด์ใหม่ที่เปรมแก้
            status='Draft',
            order_date=datetime.date.today(),
            created_by=user,
            notes=f"สร้างอัตโนมัติจาก SO: {sales_item.sales_order.so_number}"
        )
    
    @admin.action(description='⚡ เปิดใบสั่งผลิต (Auto PD)')
    def make_production_order(self, request, queryset):
        created_count = 0
        fail_list = []

        for so in queryset:
            for item in so.items.all():
                # เรียกใช้ฟังก์ชัน Engine ที่เราปรับปรุง
                new_pd = self.create_auto_production_order(item, request.user)
                
                if new_pd:
                    created_count += 1
                else:
                    fail_list.append(f"{item.product.name} ({so.so_number})")

        # สรุปผลบนแถบแจ้งเตือน
        if created_count > 0:
            self.message_user(request, f"✅ สร้างสำเร็จ {created_count} รายการ", messages.SUCCESS)
        
        if fail_list:
            msg = "⚠️ ข้ามรายการที่ไม่มี BOM: " + ", ".join(fail_list)
            self.message_user(request, msg, messages.WARNING)
            
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

    def get_confirmed_status(self, obj):
        # ไปแอบดูใน Log ว่ามีการติ๊กรับชำระเงินหรือยัง
        from .models import SalesDeliveryLog # 👈 Import มาใช้ตรงๆ
        
        # ใช้ obj (ที่เป็น SalesOrder) ไปหาใน Log
        confirmed = SalesDeliveryLog.objects.filter(
            sales_order=obj, 
            is_revenue_confirmed=True
        ).exists()
        
        if confirmed:
            return format_html('<span style="color:green;"><b>✔ ยืนยันยอดจากใบส่งของแล้ว</b></span>')
        return format_html('<span style="color:gray;">รอยืนยันยอด</span>')
        
    get_confirmed_status.short_description = "สถานะการตรวจสอบ"

    def has_change_permission(self, request, obj=None):
        if obj:
            # 🔒 เปลี่ยนจากเช็ก Confirmation เป็นเช็กสถานะใบสั่งขาย
            if obj.status == 'Completed':
                return False # ล็อคเฉพาะตอนกด "เสร็จงาน/ปิดงาน" เท่านั้น
        return super().has_change_permission(request, obj)
    
class ProductionMaterialUsageInline(admin.TabularInline):
    model = ProductionMaterialUsage
    extra = 0
    fields = ['raw_material', 'planned_qty', 'actual_qty_to_use', 'used_so_far']
    readonly_fields = ['planned_qty', 'used_so_far'] # สองฟิลด์นี้ให้ระบบคำนวณเอง
    verbose_name = "ส่วนประกอบ/Package ตามสูตร"

@admin.register(ProductionOrder)
class ProductionOrderAdmin(DocumentLockMixin,admin.ModelAdmin):
    fields = ['product', 'bom', 'quantity_planned', 'status', 'notes']
    list_display = ('pd_number', 'product', 'quantity_planned', 'quantity_actual', 'get_diff', 'status')
    list_filter = ('status', 'order_date', 'product')
    search_fields = ('pd_number', 'product__name')
    inlines = [ProductionMaterialUsageInline,ProductionLogInline]
    date_hierarchy = 'order_date' # ✅ เพิ่มบรรทัดนี้ค่ะ
    readonly_fields = ('pd_number','quantity_actual',  'created_by', 'status') 
    
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
        # 🎯 1. สำหรับฟิลด์ Product: กรองเอาเฉพาะสินค้าที่มีการติ๊ก 'มี BOM'
        if db_field.name == "product":
            kwargs["queryset"] = Product.objects.filter(has_bom=True)

        # 🎯 2. สำหรับฟิลด์ BOM: กรองสูตรผลิตให้ตรงกับตัวสินค้าที่เลือกในใบนี้
        # หมายเหตุ: ใน Inline ของ Django ตัวแปร 'obj' คือตัวแม่ (Parent) จะถูกส่งมาทาง kwargs
        obj = kwargs.get('obj') 
        if db_field.name == "bom" and obj and hasattr(obj, 'product'):
            kwargs["queryset"] = BOM.objects.filter(product=obj.product)

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
    search_fields = ('name', 'barcodes__code', 'tags__name')
    # 🎯 1. แผนรับ (PO): สั่ง - รับจริง (รวม Draft)

    def get_pending_in(self, obj):
        from .models import PurchaseItem
        
        # ✅ รวมทุกสถานะที่ "ของยังมาไม่ถึงมือ" (เพื่อให้หน้า C1 แม่นยำที่สุด)
        items = PurchaseItem.objects.filter(
            product=obj,
            purchase_order__status__in=[
                'Draft', 'Confirmed', 'Ordered', 'Paid', 
                'Loaded', 'Departed', 'Arrived', 'Received'
            ]
        )
        
        # 🎯 สูตร: รวมส่วนต่าง (Ordered - Received) ของทุกใบที่ยังไม่ปิดงาน
        total = sum(
            (i.quantity_ordered - i.quantity_received) 
            for i in items 
            if (i.quantity_ordered or 0) > (i.quantity_received or 0)
        )
        
        return total if total > 0 else 0

    get_pending_in.short_description = "แผนรับ (PO)"

    # 🎯 2. แผนส่ง (SO): สั่ง - ส่งจริง (รวม Draft)
    def get_pending_out(self, obj):
        from .models import SalesItem # 👈 เรียกใช้ Model ตรงๆ
        items = SalesItem.objects.filter(
            product=obj,
            sales_order__status__in=['Draft', 'Confirmed', 'Shipped']
        )
        # คำนวณส่วนต่าง (ค้างส่ง)
        total = sum((i.quantity_ordered - i.quantity_shipped) for i in items)
        return total if total > 0 else 0
    get_pending_out.short_description = "แผนส่ง (SO)"

    # 3. แก้ไขแผนผลิต (PD): ให้ครอบคลุมทุกสถานะที่ยังผลิตไม่เสร็จ
    # 3. แก้ไขแผนผลิต (PD): ครอบคลุมทั้งยอด "รอรับ" และยอด "รอใช้ (จอง)"
    def get_pending_prod(self, obj):
        from .models import ProductionOrder, ProductionMaterialUsage
        from django.db.models import Sum, F
        
        # 🎯 ขาที่ 1: ยอดรอรับ (สำหรับสินค้า C ที่เราผลิตเอง)
        orders = ProductionOrder.objects.filter(
            product=obj,
            status__in=['Draft', 'Started', 'Finished']
        )
        # ส่วนต่างที่ยังผลิตไม่ครบ
        pending_receipt = sum((o.quantity_planned - o.quantity_actual) for o in orders)
        
        # 🎯 ขาที่ 2: ยอดรอใช้ (สำหรับสินค้า A, B ที่ถูกจองไปใช้ในใบผลิต)
        usages = ProductionMaterialUsage.objects.filter(
            raw_material=obj,
            production_order__status__in=['Draft', 'Started', 'Finished']
        )
        # ส่วนต่างที่จองไว้แต่ยังไม่ได้ตัดสต็อกจริง
        pending_usage = sum((u.actual_qty_to_use - u.used_so_far) for u in usages)
        
        # ผลรวมสุทธิ: (รอรับเข้ามา) - (รอใช้หายไป)
        # ถ้าเป็น A, B ค่าจะออกมาเป็น "ติดลบ" เช่น -5000 เพื่อโชว์ว่าโดนจอง
        net_impact = pending_receipt - pending_usage
        
        if net_impact == 0: return 0
        
        color = "#28a745" if net_impact > 0 else "#dc3545" # เขียวถ้าเพิ่ม แดงถ้าลด
        return format_html('<span style="color: {};">{}</span>', color, net_impact)

    get_pending_prod.short_description = "แผนผลิต (PD)"

    # 🎯 แก้ไขสูตรคาดการณ์ (Plan) ให้รองรับเลขติดลบจาก PD
    def get_available(self, obj):
        # ดึงค่าดิบๆ มาคำนวณ (ต้องแก้ฟังก์ชัน get_pending_prod ให้คืนค่าตัวเลขด้วย หรือแยกดึงค่า)
        on_hand = obj.stock_quantity
        p_in = self.get_pending_in(obj)
        p_out = self.get_pending_out(obj)
        
        # ดึงยอดสุทธิจาก PD (เขียนแยกมาเพื่อใช้คำนวณ)
        p_receipt = sum((o.quantity_planned - o.quantity_actual) for o in obj.productionorder_set.filter(status__in=['Draft', 'Started', 'Finished']))
        from .models import ProductionMaterialUsage
        p_usage = sum((u.actual_qty_to_use - u.used_so_far) for u in ProductionMaterialUsage.objects.filter(raw_material=obj, production_order__status__in=['Draft', 'Started', 'Finished']))
        
        # สูตร: Stock + PO - SO + (รอรับ - รอใช้)
        total = on_hand + p_in - p_out + (p_receipt - p_usage)
        
        color = "red" if total < 0 else "blue"
        return format_html('<b style="color: {};">{}</b>', color, total)
    get_available.short_description = "คาดการณ์ (Plan)"

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
        initial=timezone.now,
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
class FinanceReportAdmin(DocumentLockMixin,admin.ModelAdmin):
    # หน้ารวม: ดูง่ายๆ ว่าใบไหนค้างจ่าย
    search_fields = ('po_number', 'supplier__company_name')
    actions = [settle_and_close_orders, settle_purchase_special, 'calculate_finance_totals']

    @admin.action(description="📝 สรุปยอดเงินรายจ่ายที่เลือก")
    def calculate_finance_totals(self, request, queryset):
        grand_total = 0
        paid_total = 0
        total_balance_due = 0 # ✅ ใช้ชื่อให้ตรงกับ Balance Due ในหน้าจอ

        for obj in queryset:
            grand_total += float(obj.grand_total or 0)
            paid_total += float(obj.total_paid or 0)
            total_balance_due += float(obj.balance_due or 0)

        summary_message = (
            f"📊 สรุปรายจ่าย {queryset.count()} รายการ:  |  "
            f"💰 ยอดจ่ายสุทธิรวม: {grand_total:,.2f} บาท  |  "
            f"✅ จ่ายแล้วรวม: {paid_total:,.2f} บาท  |  "
            f"❗️ ค้างจ่ายรวม (Balance Due): {total_balance_due:,.2f} บาท"
        )
        self.message_user(request, summary_message, messages.SUCCESS)

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
class IncomeReportAdmin(DocumentLockMixin, admin.ModelAdmin):
    # ✅ ปรับ list_display ให้เอาตัวที่มีสีมาโชว์เลย จะได้ดูง่ายๆ
    list_display = ('so_number', 'customer', 'get_grand_total_display', 'get_balance_due_display', 'payment_status')
    list_filter = ('payment_status', 'status', 'customer', 'order_date')
    search_fields = ('so_number', 'customer__company_name')
    actions = [settle_and_close_orders, settle_income_special, 'calculate_income_totals']

    @admin.action(description="📝 สรุปยอดเงินรายรับที่เลือก")
    def calculate_income_totals(self, request, queryset):
        grand_total = 0
        paid_total = 0
        total_balance_due = 0 # ✅ เปลี่ยนชื่อจาก balance_total เป็นชื่อนี้ให้อ่านง่าย
        
        for obj in queryset:
            grand_total += float(obj.grand_total or 0)
            paid_total += float(obj.total_paid or 0)
            # ✅ เรียกใช้ฟังก์ชันคำนวณที่เปรมมีอยู่แล้วใน Admin
            total_balance_due += float(self.calculate_balance_due(obj) or 0)

        summary_message = (
            f"💰 สรุปรายรับ {queryset.count()} รายการ: | "
            f"ยอดสุทธิ: {grand_total:,.2f} | "
            f"รับเงินแล้ว: {paid_total:,.2f} | "
            f"⚠️ ค้างรับ (Balance Due): {total_balance_due:,.2f}" # ✅ ใช้คำให้ตรงกับหน้าจอ
        )
        self.message_user(request, summary_message, messages.SUCCESS)

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

    # 🎯 1. ฟังก์ชันช่วยคำนวณยอดรับ (เฉพาะยอดบวก) เพื่อไม่ให้ค่าใช้จ่ายมาดึงยอด Paid ลง
    def get_revenue_only_paid(self, obj):
        from django.db.models import Sum
        # ✅ ใช้ .payments เพราะเป็น related_name ที่เปรมตั้งไว้
        total = obj.payments.filter(amount__gt=0).aggregate(Sum('amount'))['amount__sum'] or 0
        return total

    # 🎯 2. แก้ไขการแสดงผลยอดรับเงิน
    def get_total_paid_display(self, obj):
        # เปลี่ยนจาก obj.total_paid มาใช้ฟังก์ชันใหม่ที่เราสร้าง
        paid_amount = self.get_revenue_only_paid(obj)
        value = f"{paid_amount:,.2f}"
        return format_html('<b style="color:#28a745;">{}</b>', value)
    get_total_paid_display.short_description = "✅ รับแล้ว"

    # 🎯 3. แก้ไขการคำนวณยอดคงค้าง (Balance Due)
    def calculate_balance_due(self, obj):
        subtotal = getattr(obj, 'total_items_price', 0) or 0
        vat_p = getattr(obj, 'vat_percent', 0) or 0
        # ยอดรวมภาษี (Grand Total)
        grand_total = subtotal + (subtotal * vat_p / 100)
        
        # หักเฉพาะยอดที่รับเงินมาจริง (ยอดบวก) ไม่เอา DC/Rebate มาลบซ้ำที่นี่
        paid = self.get_revenue_only_paid(obj)
        
        return grand_total - paid

    # 🎯 4. (แถม) ฟังก์ชันดูยอดที่โดนหักไป (DC + Rebate) เพื่อความโปร่งใส
    def get_total_deductions_display(self, obj):
        from django.db.models import Sum
        # ✅ ใช้ .payments และกรองเฉพาะยอดติดลบ (DC/Rebate)
        total = obj.payments.filter(amount__lt=0).aggregate(Sum('amount'))['amount__sum'] or 0
        return format_html('<span style="color:#6c757d;">{:,.2f}</span>', total)
    get_total_deductions_display.short_description = "➖ ยอดหักสะสม"

#@admin.register(ShipmentPaymentReport)
class ShipmentPaymentReportAdmin(admin.ModelAdmin):
    # ✅ โชว์มูลค่าที่ส่ง และวันที่จะได้รับเงินของยอดนั้นๆ
    list_display = ['payment_due_date', 'get_so_number', 'get_customer', 'quantity_shipped', 'get_shipment_value_display', 'get_dc_display','get_rebate_display', 'get_total_with_vat_display']
    search_fields = ['sales_order__so_number', 'sales_order__customer__company_name']
    list_filter = ['payment_due_date', 'sales_order__customer']
    ordering = ['payment_due_date']

    actions = ['calculate_selected_totals']
    
    list_display = [
        'payment_due_date', 'get_so_number', 'get_customer', 
        'quantity_shipped', 'get_shipment_value_display', 
        'get_dc_display', 'get_rebate_display', 'get_total_with_vat_display'
    ]

    # --- 🧮 ฟังก์ชันคำนวณยอดรวมสำหรับรายการที่เลือก ---
    @admin.action(description="📝 สรุปยอดรวมรายการที่เลือก")
    def calculate_selected_totals(self, request, queryset):
        # 1. สั่งให้ฐานข้อมูลคำนวณ Sum ทุกคอลัมน์พร้อมกัน
        totals = queryset.aggregate(
            total_qty=Sum('quantity_shipped'),
            total_value=Sum('shipment_value'),
            total_dc=Sum('dc_amount'),
            total_rebate=Sum('rebate_amount'),
        )

        # 2. คำนวณยอดสุทธิ (คิด VAT 7%)
        net_before_vat = (totals['total_value'] or 0) - (totals['total_dc'] or 0) - (totals['total_rebate'] or 0)
        total_with_vat = float(net_before_vat) * 1.07 # หรือใช้ logic VAT จาก SO ของเปรม

        # 3. สร้างข้อความสรุป
        summary_message = (
            f"📊 สรุปยอดรวม {queryset.count()} รายการที่เลือก:  |  "
            f"📦 จำนวนรวม: {totals['total_qty'] or 0:,} ชิ้น  |  "
            f"💰 ยอดรวมสินค้า: {totals['total_value'] or 0:,.2f} บาท  |  "
            f"🔻 หัก DC: {totals['total_dc'] or 0:,.2f} บาท  |  "
            f"🔻 หัก Rebate: {totals['total_rebate'] or 0:,.2f} บาท  |  "
            f"✅ ยอดรับสุทธิ (รวม VAT): {total_with_vat:,.2f} บาท"
        )

        # 4. ส่งข้อความไปโชว์ที่หน้าจอ
        self.message_user(request, summary_message, messages.SUCCESS)

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
class CustomerProductContractAdmin(DocumentLockMixin,admin.ModelAdmin):
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

# แก้ไขบรรทัดสุดท้ายของไฟล์ admin.py จากเดิมเป็นชุดนี้ค่ะ

@admin.register(Customer)
class CustomerAdmin(DocumentLockMixin, admin.ModelAdmin): # ✅ ใส่ Mixin เพื่อล็อคหน้าจอด้วย
    # 1. กำหนดคอลัมน์ที่อยากเห็นหน้าตาราง (จะได้ไม่ต้องกดเข้าไปดูข้างใน)
    list_display = ('company_name', 'contact_person', 'phone')
    
    # 2. เพิ่มช่องค้นหา (Search) ด้านบน
    # จะช่วยให้เปรมพิมพ์ชื่อบริษัท หรือเบอร์โทรเพื่อหาลูกค้าได้ทันที
    search_fields = ('company_name', 'contact_person', 'phone')
    
    # 3. (แถม) ถ้ามีรายการราคาสัญญาลูกค้า (Contract) อยากให้โชว์ในหน้านี้เลยไหมคะ?
    # ถ้าอยากให้โชว์ ให้เอาคอมเมนต์ออกได้เลยค่ะ
    from .models import CustomerProductContract
    class ContractInline(admin.TabularInline):
        model = CustomerProductContract
        extra = 0
    inlines = [ContractInline]

@admin.register(SalesReport)
class SalesReportAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'get_total_qty', 'get_total_revenue', 
        'get_total_cost_buy', 'get_total_cost_bom', 'get_profit_margin'
    )
    list_filter = (DatePeriodFilter, 'category', 'tags',('sales_items__sales_order__customer', admin.RelatedOnlyFieldListFilter), # Path: salesitem -> sales_order -> customer
    )
    search_fields = ('name', 'barcodes__code', 'sales_items__sales_order__customer__company_name') # Path: customer__company_name

    # --- ให้การค้นหา ใช้ รูปแบบ และ หรือ ได้ ---
    def get_search_results(self, request, queryset, search_term):
        # ถ้าคนหาใช้เครื่องหมาย | ให้แยกคำแล้วใช้ Logic OR
        if '|' in search_term:
            import operator
            from django.db.models import Q
            from functools import reduce

            parts = [p.strip() for p in search_term.split('|') if p.strip()]
            # สร้าง Query แบบ (field1 OR field2) OR (field1 OR field2)
            q_objects = []
            for part in parts:
                q_part = Q()
                for field in self.search_fields:
                    q_part |= Q(**{f"{field}__icontains": part})
                q_objects.append(q_part)
            
            queryset = queryset.filter(reduce(operator.or_, q_objects))
            return queryset, False
        
        # ถ้าไม่มี | ก็ให้ทำงานแบบปกติ (AND)
        return super().get_search_results(request, queryset, search_term)

    actions = ['calculate_selected_totals']

    @admin.action(description="📝 สรุปยอดรวมรายการที่เลือก")
    def calculate_selected_totals(self, request, queryset):
        from django.db.models import Sum
        
        # ดึงผลรวมจากตัวแปรที่เราคำนวณไว้ใน get_queryset (total_qty และ total_sales_val)
        # เนื่องจากเป็นค่าจากการ annotate เราสามารถใช้ Sum() ซ้ำใน aggregate ได้เลยครับ
        totals = queryset.aggregate(
            sum_qty=Sum('total_qty'),
            sum_revenue=Sum('total_sales_val')
        )

        total_qty = totals['sum_qty'] or 0
        total_revenue = totals['sum_revenue'] or 0
        count = queryset.count()

        # แสดงผลเป็นแถบข้อความสีฟ้า (Info Message) ด้านบน
        self.message_user(
            request,
            f"📊 สรุปข้อมูลที่เลือก ({count} รายการ): "
            f"ส่งสำเร็จรวม: {total_qty:,.0f} ชิ้น | "
            f"ยอดขายรวม: ฿{total_revenue:,.2f}",
            messages.INFO
        )

    def get_queryset(self, request):
        # 1. ตั้งต้นที่สินค้า (Proxy Model)
        qs = super().get_queryset(request)
        
        period = request.GET.get('period', '1year')
        now = timezone.now()
        
        # 2. สร้างเงื่อนไขการกรอง (เน้นที่ยอดส่งสำเร็จเท่านั้น)
        # กรองสถานะใบสั่งซื้อที่ยอมรับได้
        date_query = Q(sales_order__status__in=['Shipped', 'Completed', 'ปิดงาน/ครบถ้วน', 'ส่งบางส่วน'])
        
        if period == '1year':
            date_query &= Q(sales_order__order_date__year=now.year)
        elif period == '4months':
            date_query &= Q(sales_order__order_date__gte=now - timedelta(days=120))
        elif period == '1month':
            date_query &= Q(sales_order__order_date__gte=now - timedelta(days=30))

        # 3. ใช้ Subquery เพื่อคำนวณยอด "ส่งสำเร็จ" (quantity_shipped) โดยเฉพาะ
        # วิธีนี้จะดึงยอด 700 มาโชว์ (ไม่ใช่ 2,100 และไม่เบิ้ลเป็น 6,300)
        shipped_subquery = SalesItem.objects.filter(
            product=OuterRef('pk'),
            **{f"{k}": v for k, v in date_query.children} # ส่งเงื่อนไข Shipped และวันที่เข้าไป
        ).values('product').annotate(
            total=Sum('quantity_shipped') # 🎯 เปลี่ยนจาก ordered เป็น shipped ตรงนี้ครับ!
        ).values('total')

        revenue_subquery = SalesItem.objects.filter(
            product=OuterRef('pk'),
            **{f"{k}": v for k, v in date_query.children}
        ).values('product').annotate(
            total=Sum(
                F('sale_price') * F('quantity_shipped'), # 🎯 คำนวณรายได้จากยอดส่งจริงเท่านั้น
                output_field=DecimalField()
            )
        ).values('total')

        # 4. เอาค่าที่บวกได้มาแปะในรายงาน
        return qs.annotate(
            total_qty=Subquery(shipped_subquery),
            total_sales_val=Subquery(revenue_subquery)
        ).filter(total_qty__gt=0) # 🎯 โชว์เฉพาะสินค้าที่ "ส่งสำเร็จ" จริงๆ ในรอบนั้นๆ
    
    # 🎯 หัวใจหลัก: คำนวณยอดรวมของทั้งหน้า (Grand Total)
    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        
        try:
            # ดึงข้อมูลมาคำนวณ
            cl = response.context_data['cl']
            qs = cl.get_queryset(request)
            
            aggregates = qs.aggregate(
                g_qty=Sum('total_qty'),
                g_rev=Sum('total_sales_val'),
                g_buy_cost=Sum(F('buy_price') * F('total_qty'), output_field=DecimalField())
            )

            # คำนวณ BOM (Property)
            g_bom_cost = sum(Decimal(str(p.production_cost_avg or 0)) * (p.total_qty or 0) for p in qs)
            
            g_rev = aggregates['g_rev'] or 0
            g_buy_cost = aggregates['g_buy_cost'] or 0
            g_profit = g_rev - g_buy_cost

            summary = {
                "qty": "{:,.0f}".format(aggregates['g_qty'] or 0),
                "rev": "{:,.2f}".format(g_rev),
                "buy": "{:,.2f}".format(g_buy_cost),
                "bom": "{:,.2f}".format(g_bom_cost),
                "profit": "{:,.2f}".format(g_profit)
            }
            
            # ✅ ใช้ปีกกาคู่ {{ }} สำหรับส่วนที่เป็น JavaScript แท้ๆ 
            # และใช้ {variable} สำหรับส่วนที่ดึงมาจาก Python
            summary_json = json.dumps(summary)
            js_code = """
                <script>
                    document.addEventListener('DOMContentLoaded', function() {{
                        const data = {0};
                        const table = document.querySelector('#result_list');
                        if (table) {{
                            const tfoot = document.createElement('tfoot');
                            tfoot.innerHTML = `
                                <tr style="font-weight: bold; background: #f8f9fa; border-top: 2px solid #dee2e6;">
                                    <td style="color: #333;">ยอดรวมทั้งหมด (TOTAL)</td>
                                    <td>${{data.qty}}</td>
                                    <td>${{data.rev}}</td>
                                    <td>${{data.buy}}</td>
                                    <td>${{data.bom}}</td>
                                    <td style="color: ${{parseFloat(data.profit.replace(/,/g, '')) >= 0 ? '#28a745' : '#dc3545'}}">
                                        ${{data.profit}}
                                    </td>
                                </tr>
                            `;
                            table.appendChild(tfoot);
                        }}
                    }});
                </script>
            """.format(summary_json) # ✅ ใช้ .format แทน f-string เพื่อความชัวร์

            extra_context = extra_context or {}
            extra_context['summary_js'] = mark_safe(js_code)
            return super().changelist_view(request, extra_context)
            
        except Exception as e:
            # ถ้าเกิด Error ให้รันหน้าปกติไปก่อน ไม่ต้องค้าง
            print(f"Error in C5 Total: {e}")
            return response
        
    # --- ฟังก์ชันแสดงผลรายบรรทัด (เหมือนเดิม) --- -
    @admin.display(description="จำนวนขาย")
    def get_total_qty(self, obj): return f"{obj.total_qty or 0:,.0f} {obj.unit}"

    @admin.display(description="ยอดขายรวม")
    def get_total_revenue(self, obj): return f"{obj.total_sales_val or 0:,.2f}"

    @admin.display(description="ต้นทุนรวม (Buy)")
    def get_total_cost_buy(self, obj):
        return f"{(obj.buy_price or 0) * (obj.total_qty or 0):,.2f}"

    @admin.display(description="ต้นทุน BOM")
    def get_total_cost_bom(self, obj):
        cost = Decimal(str(obj.production_cost_avg or 0)) * (obj.total_qty or 0)
        return f"{cost:,.2f}"

    @admin.display(description="กำไร (vs Buy)")
    def get_profit_margin(self, obj):
        revenue = obj.total_sales_val or 0
        buy_cost = (obj.buy_price or 0) * (obj.total_qty or 0)
        profit = revenue - buy_cost
        color = "#28a745" if profit > 0 else "#dc3545"
        profit_display = "{:,.2f}".format(profit)
        return format_html('<b style="color: {};">{}</b>', color, profit_display)


# 2. ตั้งค่า Admin ตัวเดียวจบ
@admin.register(ShipmentAccounting)
class ShipmentAccountingAdmin(admin.ModelAdmin):
    # ✅ เพิ่ม Action ที่ต้องการให้โชว์แยกกันใน List นี้ครับ
    actions = [
        'confirm_selected_items', 
        'confirm_revenue_only', 
        'confirm_dc_only', 
        'confirm_rebate_only',
        'calculate_selected_totals'
    ]

    list_display = (
        'short_shipped_date', 'get_so_number', 'product', 'quantity_shipped', 
        'get_revenue_no_vat', 'get_revenue_inc_vat', 
        'get_dc_value', 'get_rebate_value',
        'is_revenue_confirmed', 'is_dc_confirmed', 'is_rebate_confirmed'
    )
    
    list_filter = (
        ('shipped_date', admin.DateFieldListFilter), 
        'is_revenue_confirmed', 'is_dc_confirmed', 'is_rebate_confirmed',
        'sales_order__customer'
    )
    
    search_fields = ('sales_order__so_number', 'product__name', 'product__barcodes__code') 
    ordering = ('-shipped_date', 'sales_order__so_number')

    # --- ให้การค้นหา ใช้ รูปแบบ และ หรือ ได้ ---
    def get_search_results(self, request, queryset, search_term):
        # ถ้าคนหาใช้เครื่องหมาย | ให้แยกคำแล้วใช้ Logic OR
        if '|' in search_term:
            import operator
            from django.db.models import Q
            from functools import reduce

            parts = [p.strip() for p in search_term.split('|') if p.strip()]
            # สร้าง Query แบบ (field1 OR field2) OR (field1 OR field2)
            q_objects = []
            for part in parts:
                q_part = Q()
                for field in self.search_fields:
                    q_part |= Q(**{f"{field}__icontains": part})
                q_objects.append(q_part)
            
            queryset = queryset.filter(reduce(operator.or_, q_objects))
            return queryset, False
        
        # ถ้าไม่มี | ก็ให้ทำงานแบบปกติ (AND)
        return super().get_search_results(request, queryset, search_term)

    # --- 📅 จัดการวันที่ ---
    def short_shipped_date(self, obj):
        if obj.shipped_date:
            return obj.shipped_date.strftime('%d/%m/%y %H:%M')
        return "-"
    short_shipped_date.short_description = "วันที่ส่ง"
    short_shipped_date.admin_order_field = 'shipped_date'

    @admin.action(description="📝 สรุปยอดรวมรายการที่เลือก (เฉพาะที่ติ๊ก)")
    def calculate_selected_totals(self, request, queryset):
        total_qty = 0
        total_revenue = Decimal('0')
        total_dc = Decimal('0')
        total_rebate = Decimal('0')
        count = queryset.count()

        for obj in queryset:
            # ดึงข้อมูลสินค้าเพื่อเอาราคาขาย
            item = obj.sales_order.items.filter(product=obj.product).first()
            if item:
                qty = obj.quantity_shipped
                rev = item.sale_price * qty
                
                total_qty += qty
                total_revenue += rev
                
                # ดึง Contract เพื่อคำนวณ DC/Rebate
                from .models import CustomerProductContract
                c = CustomerProductContract.objects.filter(
                    customer=obj.sales_order.customer, 
                    product=obj.product
                ).first()
                
                if c:
                    total_dc += (rev * c.dc_percent) / Decimal('100')
                    total_rebate += (rev * c.rebate_percent) / Decimal('100')

        # แสดงผลลัพธ์เป็นข้อความ Alert สีเขียวด้านบน
        msg = (
            f"✅ สรุป {count} รายการที่เลือก: "
            f"จำนวนรวม: {total_qty:,} ชิ้น | "
            f"ยอดรวม VAT: ฿{total_revenue:,.2f} | "
            f"DC: ฿{total_dc:,.2f} | "
            f"Rebate: ฿{total_rebate:,.2f}"
        )
        self.message_user(request, msg, messages.SUCCESS)

    # --- 📊 สรุปยอดเงิน (Banner สีเหลือง) ---
    def changelist_view(self, request, extra_context=None):
        cl = self.get_changelist_instance(request)
        qs = cl.get_queryset(request)
        
        sum_vat = sum_dc = sum_rebate = Decimal('0') # ใช้ Decimal ป้องกัน Error
        for obj in qs:
            item = obj.sales_order.items.filter(product=obj.product).first()
            if item:
                rev = item.sale_price * obj.quantity_shipped
                sum_vat += rev
                from .models import CustomerProductContract
                c = CustomerProductContract.objects.filter(customer=obj.sales_order.customer, product=obj.product).first()
                if c:
                    sum_dc += (rev * c.dc_percent) / Decimal('100')
                    sum_rebate += (rev * c.rebate_percent) / Decimal('100')

        if qs.exists():
            msg = f"📊 สรุปยอดช่วงที่เลือก: ยอดรวม ฿{sum_vat:,.2f} | DC ฿{sum_dc:,.2f} | Rebate ฿{sum_rebate:,.2f}"
            messages.info(request, msg)

        return super().changelist_view(request, extra_context=extra_context)

    # --- 💰 ฟังก์ชันคำนวณเงินต่างๆ ---
    def get_revenue_inc_vat(self, obj):
        return f"{obj.calculate_revenue_total():,.2f}" # ✅ เรียกจาก Model สั้นๆ
    get_revenue_inc_vat.short_description = "ยอดรวม VAT"

    def get_revenue_no_vat(self, obj):
        item = obj.sales_order.items.filter(product=obj.product).first()
        if item:
            # 🎯 ไม่ต้องหาร vat_divisor แล้วครับ เพราะราคา item.sale_price คือราคา Non-VAT อยู่แล้ว
            no_vat = item.sale_price * obj.quantity_shipped
            return f"{no_vat:,.2f}"
        return "0.00"
    get_revenue_no_vat.short_description = "ยอด Non-VAT"

    def get_dc_value(self, obj):
        from .models import CustomerProductContract
        contract = CustomerProductContract.objects.filter(
            customer=obj.sales_order.customer, 
            product=obj.product
        ).first()
        
        if contract:
            item = obj.sales_order.items.filter(product=obj.product).first()
            revenue = (item.sale_price * obj.quantity_shipped) if item else Decimal('0')
            dc_amt = (revenue * contract.dc_percent) / Decimal('100')
            
            # ✅ แก้ตรงนี้: ฟอร์แมตตัวเลขข้างนอกก่อนส่งเข้า format_html
            formatted_amt = f"{dc_amt:,.2f}"
            return format_html('{}% (<b>฿{}</b>)', contract.dc_percent, formatted_amt)
        return "-"
    get_dc_value.short_description = "ยอด DC"

    # 🎯 4. ยอด Rebate (แก้ไขจุดที่ทำให้เกิด ValueError)
    def get_rebate_value(self, obj):
        from .models import CustomerProductContract
        contract = CustomerProductContract.objects.filter(
            customer=obj.sales_order.customer, 
            product=obj.product
        ).first()
        
        if contract:
            item = obj.sales_order.items.filter(product=obj.product).first()
            revenue = (item.sale_price * obj.quantity_shipped) if item else Decimal('0')
            reb_amt = (revenue * contract.rebate_percent) / Decimal('100')
            
            # ✅ แก้ตรงนี้เช่นกันครับ
            formatted_amt = f"{reb_amt:,.2f}"
            return format_html('{}% (<b>฿{}</b>)', contract.rebate_percent, formatted_amt)
        return "-"
    get_rebate_value.short_description = "ยอด Rebate"

    # 🎯 5. ยอด ที่ยืนยันทั้งหมด จะถูกบันทึกย้อนไปใน salesorder และ incomereport
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.is_revenue_confirmed:
            from .models import SalesPayment
            SalesPayment.objects.update_or_create(
                order=obj.sales_order,
                remark__icontains=f"ยอดส่งของ {obj.shipping_no}",
                defaults={
                    'amount': obj.calculate_revenue_total(), # ✅ ใช้ตัวเลขดิบๆ ไปบันทึก
                    'payment_date': obj.confirmed_date or obj.shipped_date,
                    'remark': f"✔ ยอดส่งของเลขที่ {obj.shipping_no}"
                }
            )

        # 🎯 [SECTION 2] ยืนยันยอด Rebate (รายการหัก 1)
        if obj.is_rebate_confirmed and obj.rebate_amount > 0:
            rebate_ref = f"หัก Rebate จากใบส่งของ {obj.shipping_no}"
            if not SalesPayment.objects.filter(order=obj.sales_order, notes__icontains=rebate_ref).exists():
                SalesPayment.objects.create(
                    order=obj.sales_order,
                    amount=-obj.rebate_amount, # ติดลบเพื่อหักยอด
                    payment_date=obj.confirmed_date,
                    notes=f"⚠ {rebate_ref}"
                )

        # 🎯 [SECTION 3] ยืนยันยอด DC (รายการหัก 2)
        if obj.is_dc_confirmed and obj.dc_amount > 0:
            dc_ref = f"หักค่า DC จากใบส่งของ {obj.shipping_no}"
            if not SalesPayment.objects.filter(order=obj.sales_order, notes__icontains=dc_ref).exists():
                SalesPayment.objects.create(
                    order=obj.sales_order,
                    amount=-obj.dc_amount, # ติดลบเพื่อหักยอด
                    payment_date=obj.confirmed_date,
                    notes=f"📦 {dc_ref}"
                )

    # --- ✅ Actions ---
    @admin.action(description="💰 ยืนยันเฉพาะยอดรับเงิน (Revenue)")
    def confirm_revenue_only(self, request, queryset):
        for obj in queryset:
            obj.is_revenue_confirmed = True
            # 🔥 บังคับเรียก save_model เพื่อให้สร้าง SalesPaymentLog
            self.save_model(request, obj, None, True) 
        self.message_user(request, f"ยืนยันยอดรับเงิน {queryset.count()} รายการ และสร้างประวัติเงินแล้ว")

    @admin.action(description="🚚 ยืนยันเฉพาะค่า DC")
    def confirm_dc_only(self, request, queryset):
        for obj in queryset:
            obj.is_dc_confirmed = True
            # 🔥 บังคับเรียก save_model เพื่อให้สร้างรายการหักเงิน
            self.save_model(request, obj, None, True)
        self.message_user(request, f"ยืนยันยอด DC {queryset.count()} รายการ และหักยอดจ่ายแล้ว")

    @admin.action(description="🎁 ยืนยันเฉพาะยอด Rebate")
    def confirm_rebate_only(self, request, queryset):
        for obj in queryset:
            obj.is_rebate_confirmed = True
            # 🔥 บังคับเรียก save_model เพื่อให้สร้างรายการหักเงิน
            self.save_model(request, obj, None, True)
        self.message_user(request, f"ยืนยันยอด Rebate {queryset.count()} รายการ และหักยอดจ่ายแล้ว")

    @admin.action(description="✅ ยืนยันยอดทั้งหมด (ครบทุกส่วน)")
    def confirm_selected_items(self, request, queryset):
        for obj in queryset:
            obj.is_revenue_confirmed = True
            obj.is_dc_confirmed = True
            obj.is_rebate_confirmed = True
            # สั่ง Save ทีละตัวเพื่อให้ save_model ที่เราเขียนไว้ทำงาน
            self.save_model(request, obj, None, True)
        self.message_user(request, f"ยืนยันและบันทึกประวัติการเงิน {queryset.count()} รายการแล้ว")

    def get_so_number(self, obj):
        return obj.sales_order.so_number
    get_so_number.short_description = "เลขที่ SO"

class InternationalPurchaseTracking(PurchaseOrder):
    class Meta:
        proxy = True
        verbose_name = "B4. ติดตามสินค้าต่างประเทศ (Import Tracking)"
        verbose_name_plural = "B4. ติดตามสินค้าต่างประเทศ (Import Tracking)"

@admin.register(InternationalPurchaseTracking)
class InternationalPurchaseTrackingAdmin(admin.ModelAdmin):
    # เพิ่ม related_po เข้ามาในตารางด้วยเพื่อให้เห็นว่าลิ้งก์กับใบไหน
    list_display = ('po_number', 'related_po', 'supplier', 'display_tracking_table', 'status')
    list_filter = ('status', 'supplier', 'order_date') # กรองตามวันที่ได้ด้วย
    search_fields = ('po_number', 'related_po__po_number', 'supplier__name')

    list_select_related = ('related_po', 'supplier')

    # ✅ 1. กรองเฉพาะ: ต่างประเทศ (International) และยังไม่ปิดใบสั่งซื้อ (Closed)
    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            supplier__type='International'  # 👈 ใช้ __ เพื่อวิ่งไปดู field ใน model Supplier
        ).exclude(
            status='Closed'
        )

    def display_tracking_table(self, obj):
        milestones = [
            ('Ordered', obj.order_date),
            ('Paid', obj.paid_date), # อัปเดตตรงนี้
            ('Loaded', obj.loaded_date),
            ('Departed', obj.departed_date),
            ('Arrived', obj.arrived_date),
            ('Received', obj.received_date),
        ]
        
        headers = "".join([f"<th style='border:1px solid #ddd; padding:4px; background:#f8f9fa;'>{m[0]}</th>" for m in milestones])
        cells = ""
        for name, date in milestones:
            date_str = date.strftime('%d/%m/%y') if date else "-"
            color = "#28a745" if obj.status == name else "#666"
            weight = "bold" if obj.status == name else "normal"
            cells += f"<td style='border:1px solid #ddd; padding:4px; color:{color}; font-weight:{weight};'>{date_str}</td>"

        return mark_safe(
            f"<table style='width:100%; text-align:center; border-collapse:collapse; font-size:10px;'>"
            f"<thead><tr>{headers}</tr></thead>"
            f"<tbody><tr>{cells}</tr></tbody></table>"
        )
    display_tracking_table.short_description = "📅 Timeline การส่งมอบ"

    # ✅ 5. Actions: ขยับสถานะ Milestone แบบรวดเร็ว (ครบชุด)
    actions = ['set_paid', 'set_loaded', 'set_departed', 'set_arrived', 'set_received', 'set_closed']

    @admin.action(description='💰 2. เปลี่ยนสถานะ: จ่ายเงินแล้ว (Paid)')
    def set_paid(self, request, queryset):
        queryset.update(status='Paid', paid_date=timezone.now().date())

    @admin.action(description='📦 3. เปลี่ยนสถานะ: ขึ้นตู้แล้ว (Loaded)')
    def set_loaded(self, request, queryset):
        queryset.update(status='Loaded', loaded_date=timezone.now().date())

    @admin.action(description='🚢 4. เปลี่ยนสถานะ: ออกเดินทาง (Departed)')
    def set_departed(self, request, queryset):
        queryset.update(status='Departed', departed_date=timezone.now().date())

    @admin.action(description='🏁 5. เปลี่ยนสถานะ: ถึงไทยแล้ว (Arrived)')
    def set_arrived(self, request, queryset):
        queryset.update(status='Arrived', arrived_date=timezone.now().date())

    @admin.action(description='🏢 6. เปลี่ยนสถานะ: ถึงโกดังแล้ว (Received)')
    def set_received(self, request, queryset):
        queryset.update(status='Received', received_date=timezone.now().date())

    @admin.action(description='🔒 7. ปิดใบสั่งซื้อ (Closed/ซ่อนรายการ)')
    def set_closed(self, request, queryset):
        queryset.update(status='Closed')
        
