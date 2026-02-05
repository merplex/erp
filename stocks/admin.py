from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.core.exceptions import ValidationError
from django.forms import TextInput
from django.db import models # เพิ่มเพื่อรองรับ formfield_overrides
from .models import *
from django import forms # ✅ เพิ่มบรรทัดนี้ครับ ทำระบบ tag checkbox
from django.db.models import F
from django.utils.safestring import mark_safe # ✅ ต้องมีบรรทัดนี้ครับ
from django import forms # สำหรับปรับแต่งฟอร์ม tag
# เพิ่มที่บรรทัดบนสุดของไฟล์ครับ
from django.http import HttpResponseRedirect 

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
    extra = 1
    readonly_fields = ('quantity_received',) 

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            resolved = request.resolver_match
            if resolved and 'object_id' in resolved.kwargs:
                po_id = resolved.kwargs['object_id']
                try:
                    from django.db.models import Q # ✅ ต้อง Import Q มาด้วยครับ
                    po = PurchaseOrder.objects.get(pk=po_id)
                    
                    # ✅ เงื่อนไขใหม่: 
                    # 1. เป็นสินค้าที่ Supplier รายนี้ขาย (is_product=True และมีชื่อใน list)
                    # 2. หรือ เป็นรายการ "ไม่ใช่สินค้า" (is_product=False) ซึ่งใครก็ซื้อได้
                    kwargs["queryset"] = Product.objects.filter(
                        Q(product_suppliers__supplier=po.supplier) | Q(is_product=False)
                    ).distinct()
                    
                except Exception as e:
                    print(f"Error filtering PO products: {e}")
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
    # ✅ เพิ่ม 'auto_produce' เข้าไปในหน้าจอ
    fields = ['product', 'quantity_ordered', 'quantity_shipped', 'auto_produce']
    readonly_fields = ('quantity_shipped',)
    extra = 1

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

    # ✅ 1. ส่วน Media: ฉีด CSS เข้าไปทำลายสไตล์แนวตั้งของ Django
    class Media:
        # เราจะใช้เทคนิคสร้าง CSS "ปลอม" เพื่อหลอกให้ Django ยอมฉีดสไตล์ที่เราต้องการเข้าไปในหน้า
        css = {
            'all': ('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css',)
        }
        # 🔥 นี่คือไม้ตายครับ ฉีดสไตล์เข้าไปที่หน้าแก้ไขโดยตรง
        # เราจะใส่ไว้ใน widget แทนเพื่อให้ทำงานได้ 100%
        
    # ✅ 2. ส่วนจัดการ Tag: ใส่สี + เรียงแนวนอนแบบบังคับพิเศษ
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "tags":
            from django.db.models import Count
            from django.utils.safestring import mark_safe
            
            # ดึง Tag เรียงตามความนิยม
            qs = ProductTag.objects.annotate(num_products=Count('products')).order_by('-num_products', '-id')
            
            for tag in qs:
                # ใส่สีให้ Tag ตอนเลือก
                tag.name = mark_safe(
                    f'<span style="background:{tag.color}; color:white; padding:2px 10px; border-radius:10px; font-size:12px; font-weight:bold; display:inline-block;">'
                    f'{tag.name}</span>'
                )
            
            kwargs["queryset"] = qs
            # ✅ บังคับ Style ที่ตัวรายการภายใน (li) ให้เป็นแนวนอน
            kwargs["widget"] = forms.CheckboxSelectMultiple(attrs={
                'style': '''
                    display: flex !important;
                    flex-wrap: wrap !important;
                    flex-direction: row !important;
                    gap: 15px !important;
                    padding: 10px !important;
                    list-style: none !important;
                '''
            })
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    # ✅ 3. ตัวโชว์ Tag ในหน้ารวมรายการสินค้า
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

    # 1. จัดการ Logic เมื่อมีการกดปุ่ม
    def response_change(self, request, obj):
        if "_complete_order" in request.POST:
            obj.status = 'Completed'
            obj.save()
            self.message_user(request, f"ปิดงานใบสั่งซื้อ {obj.po_number} เรียบร้อยแล้ว")
            return HttpResponseRedirect(".")
        return super().response_change(request, obj)

    # 2. ฉีดปุ่มเข้าไปในหน้าจอแก้ไข
    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        # สร้าง Script เพื่อเพิ่มปุ่มในแถบด้านล่าง
        script = mark_safe("""
            <script>
                django.jQuery(document).ready(function() {
                    var container = django.jQuery('.submit-row');
                    var btn = '<input type="submit" value="เสร็จงาน (Complete)" name="_complete_order" style="background: #28a745; color: white; height: 35px; margin-right: 10px; border-radius: 4px; border: none; cursor: pointer; padding: 0 20px; font-weight: bold;">';
                    container.prepend(btn);
                });
            </script>
        """)
        # ใส่สคริปต์ลงใน context เพื่อให้ Django เรนเดอร์ออกมา
        context['adminform'].form.help_text = script 
        return super().render_change_form(request, context, add, change, form_url, obj)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_diff(self, obj):
        ordered = sum(i.quantity_ordered for i in obj.items.all())
        received = sum(l.quantity_received for l in obj.receipt_logs.all())
        return color_diff(received - ordered)
    get_diff.short_description = "สถานะรับของ"

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
        # ✅ เช็คก่อนว่าถ้าเป็น ProductionLog ให้เซฟปกติ ข้อมูลถึงจะเข้าสต็อก
        if formset.model == ProductionLog:
            instances = formset.save(commit=False)
            for instance in instances:
                if hasattr(instance, 'user'): instance.user = request.user
                instance.save()
            formset.save_m2m()
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
    list_filter = ('category', 'suppliers', BuyPriceRangeFilter)
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

@admin.register(FinanceReport)
class FinanceReportAdmin(admin.ModelAdmin):
    list_display = ('po_number', 'supplier', 'order_date', 'status')

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
    list_display = ('name', 'color_display')
    search_fields = ('name',)
    # ✅ เพิ่ม Inline เข้าไปที่นี่ค่ะ
    inlines = [ProductInTagInline]

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


admin.site.register(Customer)
