from django.contrib import admin
from django.utils.html import format_html
from django.core.exceptions import ValidationError
from django.forms import TextInput
from django.db import models # เพิ่มเพื่อรองรับ formfield_overrides
from .models import *

# --- Inlines ---
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
                    po = PurchaseOrder.objects.get(pk=po_id)
                    kwargs["queryset"] = Product.objects.filter(product_suppliers__supplier=po.supplier)
                except: pass
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
    extra = 1
    readonly_fields = ('quantity_shipped',)

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
    list_display = ('name', 'barcode', 'buy_price', 'get_production_cost', 'sale_price', 'stock_quantity', 'unit', 'has_bom', 'created_by')
    list_filter = ('category', 'has_bom', 'suppliers')
    search_fields = ('name', 'barcode')
    inlines = [ProductSupplierInline]
    readonly_fields = ('created_by', 'updated_by', 'created_at', 'updated_at')

    # 🛠️ จุดที่แก้เพื่อเลิกล่ม: ดัก Error การจัดรูปแบบตัวเลข
    def get_production_cost(self, obj):
        # 1. ดึงค่าดิบๆ ออกมาก่อน
        raw_val = getattr(obj, 'production_cost_avg', None)
        
        # 2. แฉทันที! ถ้าไม่ใช่ตัวเลข ให้โชว์หน้าเว็บเลยว่ามันคือ Type อะไร
        # (วิธีนี้จะทำให้เว็บไม่ล่ม และเราจะเห็น "ตัวการ" ทันที)
        if not isinstance(raw_val, (int, float)):
            return format_html(
                '<span style="color:red; font-weight:bold;">'
                'ไม่ใช่ตัวเลข!<br>'
                'Type: {}<br>'
                'Value: {}'
                '</span>',
                type(raw_val).__name__,
                str(raw_val)
            )
            
        # 3. ถ้ารอดมาถึงตรงนี้ แสดงว่าเป็นตัวเลขจริง ค่อยโชว์สวยๆ
        try:
            return format_html(
                '<b style="color: #28a745;">{:,.2f}</b>', 
                float(raw_val)
            )
        except Exception as e:
            return f"Err: {e}"

    get_production_cost.short_description = "ต้นทุนผลิตเฉลี่ย (BOM)"

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
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

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
    readonly_fields = ('created_by', 'status') 

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
        instances = formset.save(commit=False)
        for instance in instances:
            if hasattr(instance, 'user'): instance.user = request.user
            instance.save()
        formset.save_m2m()

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
    search_fields = ('name', 'barcode')

    def get_pending_in(self, obj):
        items = obj.purchaseitem_set.filter(purchase_order__status__in=['Confirmed', 'Received'])
        total = sum((i.quantity_ordered - i.quantity_received) for i in items)
        return total if total > 0 else 0
    get_pending_in.short_description = "แผนรับ (PO)"

    def get_pending_out(self, obj):
        items = obj.salesitem_set.filter(sales_order__status__in=['Confirmed', 'Shipped'])
        total = sum((i.quantity_ordered - i.quantity_shipped) for i in items)
        return total if total > 0 else 0
    get_pending_out.short_description = "แผนส่ง (SO)"

    def get_pending_prod(self, obj):
        orders = obj.productionorder_set.filter(status__in=['Started', 'Finished'])
        total = sum((o.quantity_planned - o.quantity_actual) for o in orders)
        return total if total > 0 else 0
    get_pending_prod.short_description = "แผนผลิต (PD)"

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

admin.site.register(ProductCategory)
admin.site.register(Customer)
