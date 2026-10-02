from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.db.models import Sum
from django.db.models.signals import post_delete, post_save
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.dispatch import receiver
import random # ✅ เพิ่มไว้บนสุดของไฟล์
import datetime
import re


def round_money(value):
    """ปัดยอดเงินเป็น 2 ตำแหน่ง (ยอดที่คิด VAT อาจมีทศนิยมเกิน แต่ช่องเงินใน DB เก็บได้แค่ 2 ตำแหน่ง)"""
    return Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class DocumentLock(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=50) # รองรับทั้ง ID ตัวเลขและเลขที่เอกสาร
    content_object = GenericForeignKey('content_type', 'object_id')
    locked_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('content_type', 'object_id')

    def is_expired(self):
        # ตั้งไว้ 10 นาที ถ้าเปิดทิ้งไว้เฉยๆ ไม่ทำอะไร 10 นาที ระบบจะปล่อยให้คนอื่นแย่งล็อกได้
        return (timezone.now() - self.locked_at).total_seconds() > 600 

    def __str__(self):
        return f"{self.user.username} ล็อก {self.content_type.model} ID:{self.object_id}"

def get_random_color():
    # สุ่มรหัสสี Hex เช่น #a1b2c3
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

# --- ฟังก์ชันช่วยรันเลขที่เอกสาร ---
def generate_number(prefix, model_class, field_name):
    today = datetime.date.today()
    date_str = today.strftime('%Y%m')
    base = f"{prefix}-{date_str}-"
    last = model_class.objects.filter(**{f"{field_name}__icontains": base}).order_by(field_name).last()
    if last:
        last_no = getattr(last, field_name).split('-')[-1]
        new_no = int(last_no) + 1
    else:
        new_no = 1
    return f"{base}{new_no:04d}"

# 1. กลุ่มสินค้า
class ProductCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name="กลุ่มสินค้า")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    def __str__(self): return self.name
    class Meta: verbose_name_plural = "W2. กลุ่มสินค้า"

class ProductTag(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="ชื่อแท็ก")
    color = models.CharField(max_length=7, default=get_random_color, verbose_name="สีแท็ก (Hex)")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="วันที่สร้าง")

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "แท็กสินค้า"
        verbose_name_plural = "W5. แท็กสินค้า (Product Tag)"

# 2. ผู้จำหน่าย
class Supplier(models.Model):
    TYPE_CHOICES = [('Domestic', 'ในประเทศ'), ('International', 'ต่างประเทศ')]
    supplier_code = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name="รหัสผู้ขาย")
    company_name = models.CharField(max_length=255, verbose_name="ชื่อบริษัท")
    contact_person = models.CharField(max_length=255, verbose_name="ชื่อคนติดต่อ")
    address = models.TextField(verbose_name="ที่อยู่")
    phone = models.CharField(max_length=50, verbose_name="เบอร์โทร")
    payment_term = models.IntegerField(default=30, verbose_name="Credit (วัน)")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='Domestic')
    vat = models.DecimalField(max_digits=5, decimal_places=2, default=7.00)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    def save(self, *args, **kwargs):
        if self.type == 'International': self.vat = 0
        # ช่องรหัสผู้ขายไม่บังคับกรอก แต่ถ้ากรอกห้ามซ้ำ — '' กับ '' ชนกันได้ใน unique constraint
        # จึงต้องแปลงค่าว่างเป็น None เพื่อให้ปล่อยว่างได้หลายรายการ
        if not self.supplier_code:
            self.supplier_code = None
        super().save(*args, **kwargs)
    def __str__(self): return self.company_name
    class Meta: verbose_name_plural = "P1. ผู้จำหน่าย (Supplier)"

# 3. ลูกค้า
class Customer(models.Model):
    buyer_code = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name="รหัสผู้ซื้อ")
    company_name = models.CharField(max_length=255, verbose_name="ชื่อบริษัท")
    contact_person = models.CharField(max_length=255, verbose_name="ชื่อคนติดต่อ")
    address = models.TextField(verbose_name="ที่อยู่")
    phone = models.CharField(max_length=50, verbose_name="เบอร์โทร")
    tax_id = models.CharField(max_length=20, blank=True, verbose_name="เลขประจำตัวผู้เสียภาษี")
    # ใช้ในรายงานภาษีขาย (คอลัมน์ "สำนักงานใหญ่/สาขา")
    branch = models.CharField(max_length=100, blank=True, default='สำนักงานใหญ่', verbose_name="สำนักงานใหญ่/สาขา")
    payment_term = models.IntegerField(default=30, verbose_name="Credit (วัน)")
    vat = models.DecimalField(max_digits=5, decimal_places=2, default=7.00)
    notes = models.TextField(blank=True, null=True, verbose_name="หมายเหตุ")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True) # แก้ไขจาก auto_True เป็น auto_now
    def save(self, *args, **kwargs):
        # ช่องรหัสผู้ซื้อไม่บังคับกรอก แต่ถ้ากรอกห้ามซ้ำ — '' กับ '' ชนกันได้ใน unique constraint
        # จึงต้องแปลงค่าว่างเป็น None เพื่อให้ปล่อยว่างได้หลายรายการ
        if not self.buyer_code:
            self.buyer_code = None
        super().save(*args, **kwargs)
    def __str__(self): return self.company_name
    account_close_day = models.IntegerField(
        default=25,
        verbose_name="วันกำหนดชำระเงิน",
        help_text="ระบุวันที่ 1-31"
    )
    factoring_account = models.ForeignKey(
        'BankAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        limit_choices_to={'account_type': 'FACTORING'}, verbose_name="บัญชีแฟคตอริ่ง",
        help_text="ใช้กับ action \"ขายแฟคตอริ่ง\" ในหน้าใบสั่งขาย/สรุปรายรับ (เลือกเป็นราย SO)")
    class Meta: verbose_name_plural = "S1. ลูกค้า (Customer)"

# 4. รายการสินค้า
class Product(models.Model):
    name = models.CharField(max_length=255, verbose_name="ชื่อสินค้า")
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True)
    # ✅ เพิ่มฟิลด์แยกประเภท (True = สินค้ามีสต็อก, False = บริการ/ค่าใช้จ่าย)
    is_product = models.BooleanField(default=True, verbose_name="เป็นสินค้ามีสต๊อก")
    tags = models.ManyToManyField(ProductTag, blank=True, related_name='products', verbose_name="แท็ก")
    suppliers = models.ManyToManyField(Supplier, through='ProductSupplier', related_name='products')
    has_bom = models.BooleanField(default=False, verbose_name="มีBOM")
    buy_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ราคาทุน (ใช้จริง)")
    auto_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, verbose_name="ต้นทุนอัตโนมัติ (Supplier+15%)")
    manual_buy_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, verbose_name="ต้นทุน (กำหนดเอง)")
    COST_SOURCE_CHOICES = [
        ('manual', 'กำหนดเอง'),
        ('bom', 'BOM'),
        ('supplier', 'Supplier +15%'),
    ]
    cost_source = models.CharField(max_length=10, choices=COST_SOURCE_CHOICES, default='supplier', blank=True, verbose_name="ที่มาต้นทุน")
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, verbose_name="ราคาขาย")
    unit = models.CharField(max_length=50, default="ชิ้น", verbose_name="หน่วย")
    stock_quantity = models.IntegerField(default=0, verbose_name="สต็อกปัจจุบัน")
    min_stock = models.PositiveIntegerField(default=0, verbose_name="สต็อกขั้นต่ำ (Min Stock)")
    production_lead_time = models.IntegerField(default=0, blank=True, null=True, verbose_name="ระยะเวลาผลิต (วัน)")
    delivery_lead_time = models.IntegerField(default=0, verbose_name="ระยะเวลาส่งมอบ (วัน)")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="prod_created")
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="prod_updated")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def save(self, *args, **kwargs):
        # manual_buy_price/auto_cost ไม่ได้ตั้ง null=True ที่ DB — ถ้าฟอร์มส่งช่องว่างมา
        # (ผู้ใช้ลบตัวเลขออกจนหมด ไม่ได้พิมพ์ 0) Django จะได้ None แล้วเซฟลง DB ไม่ได้
        # (NOT NULL constraint → error 500) จึงต้องกันไว้ตรงนี้ ให้ถือว่าว่าง = 0 เสมอ
        if self.manual_buy_price is None:
            self.manual_buy_price = Decimal('0')
        if self.auto_cost is None:
            self.auto_cost = Decimal('0')
        if not self.sale_price: self.sale_price = self.buy_price
        super().save(*args, **kwargs)
    def __str__(self): return self.name

    @property
    def production_cost_avg(self):
        if not self.has_bom:
            return 0.0
        try:
            boms = self.bom_formulas.all()
            if boms.exists():
                total_sum = sum(float(bom.total_cost) for bom in boms)
                # ส่งค่าเป็นตัวเลข float ธรรมดา ห้ามมี html
                return float(total_sum / boms.count()) 
        except:
            return 0.0
        return 0.0
        # เติมตัวนี้เข้าไปครับ แอดมินถึงจะเห็นว่ามี BOM กี่ใบ
    def _bom_unit_cost(self):
        """ต้นทุน BOM แบบ Decimal เฉลี่ยจากทุกสูตรของสินค้านี้ (ใช้เทียบกับ Supplier+15% ใน recalc_cost_and_price)"""
        if not self.has_bom:
            return Decimal('0')
        try:
            boms = list(self.bom_formulas.all())
            if not boms:
                return Decimal('0')
            total_sum = sum((bom.total_cost for bom in boms), Decimal('0'))
            return (Decimal(total_sum) / len(boms)).quantize(Decimal('0.01'))
        except Exception:
            return Decimal('0')

    @property
    def bom_count(self):
        if not self.has_bom:
            return 0
        try:
            # ใช้ related_name ตัวเดียวกับที่คำนวณราคานั่นแหละ
            return self.bom_formulas.count()
        except:
            return 0

    @property
    def latest_barcode(self):
        # ดึงบาร์โค้ดตัวล่าสุด (ลำดับสุดท้ายที่เพิ่มเข้าไป)
        # ใช้ list() แทน .last() เพื่อให้ใช้ prefetch cache ได้ (ไม่งั้น .last() จะ clone queryset ใหม่แล้วยิง query ซ้ำ)
        barcodes = list(self.barcodes.all())
        return barcodes[-1].code if barcodes else "-"

    def recalc_cost_and_price(self):
        """
        คำนวณ auto_cost (supplier ราคาสูงสุด +15%), buy_price ที่ใช้จริง และ sale_price ใหม่ แล้วบันทึกถ้ามีค่าเปลี่ยน
        ลำดับการเลือก buy_price:
          1) manual_buy_price ถ้ามีค่า (>0) → ใช้ค่านี้เสมอ (cost_source='manual')
          2) ไม่งั้นเทียบ ต้นทุน BOM เฉลี่ย (ถ้ามีสูตร) กับ auto_cost (Supplier ราคาสูงสุด +15%) แล้วใช้ค่าที่ "สูงกว่า"
             (cost_source='bom' หรือ 'supplier' ตามค่าที่ถูกเลือก)
        sale_price = max(buy_price*1.15, contract ต่ำสุด)
        คืนค่า dict {field: new_value} เฉพาะฟิลด์ที่เปลี่ยน (ว่างถ้าไม่เปลี่ยน)
        """
        if not self.pk:
            return {}

        best_supplier = self.product_suppliers.filter(
            latest_buy_price__gt=0
        ).order_by('-latest_buy_price').first()
        new_auto_cost = (
            (best_supplier.latest_buy_price * Decimal('1.15')).quantize(Decimal('0.01'))
            if best_supplier else Decimal('0')
        )

        bom_cost = self._bom_unit_cost()

        manual = self.manual_buy_price or Decimal('0')
        if manual > 0:
            new_buy = manual
            new_source = 'manual'
        elif bom_cost > new_auto_cost:
            new_buy = bom_cost
            new_source = 'bom'
        else:
            new_buy = new_auto_cost
            new_source = 'supplier'

        new_sale = self.sale_price
        if new_buy > 0:
            min_sale = (new_buy * Decimal('1.15')).quantize(Decimal('0.01'))
            lowest_contract = CustomerProductContract.objects.filter(
                product=self, contract_price__gt=0
            ).order_by('contract_price').first()
            contract_price = lowest_contract.contract_price if lowest_contract else Decimal('0')
            new_sale = max(min_sale, contract_price)

        changes = {}
        if new_auto_cost != self.auto_cost:
            changes['auto_cost'] = new_auto_cost
        if new_buy != self.buy_price:
            changes['buy_price'] = new_buy
        if new_source != self.cost_source:
            changes['cost_source'] = new_source
        if new_sale != self.sale_price:
            changes['sale_price'] = new_sale

        if changes:
            Product.objects.filter(pk=self.pk).update(**changes)
            for field, value in changes.items():
                setattr(self, field, value)

        return changes

    class Meta: verbose_name_plural = "W1. รายการสินค้า (Product)"

class ProductBarcode(models.Model):
    product = models.ForeignKey(Product, related_name='barcodes', on_delete=models.CASCADE)
    code = models.CharField(max_length=100, unique=True, verbose_name="บาร์โค้ด")
    created_at = models.DateTimeField(auto_now_add=True)
    conversion_factor = models.DecimalField(
        max_digits=10, decimal_places=4, default=1,
        validators=[MinValueValidator(Decimal('0.0001'))],
        verbose_name="จำนวนต่อหน่วย",
        help_text="เช่น 1 ถุง = 1.5234 kg ให้ใส่ 1.5234",
    )
    unit_name = models.CharField(max_length=20, blank=True, null=True, verbose_name="ชื่อหน่วย")

    def get_forecast_stock(self):
        # 1. ดึงค่า "คาดการณ์ (Plan)" จากฟังก์ชัน get_available ใน Product
        # ถ้า Product ไม่มีฟังก์ชันนี้ หรือค่าเป็น None ให้เริ่มที่ 0
        if self.product and hasattr(self.product, 'get_available'):
            available_total = self.product.get_available() or 0
        else:
            # สำรองไว้เผื่อเรียกผ่าน field stock_quantity โดยตรง
            available_total = getattr(self.product, 'stock_quantity', 0) or 0
        
        factor = self.conversion_factor or 1
        
        # 2. คำนวณแบบปัดเศษทิ้ง (ขายได้กี่หน่วยเต็ม)
        # ใช้ max(0, ...) เพื่อไม่ให้โชว์สต็อกติดลบให้ลูกค้าตกใจ
        forecast_qty = max(0, available_total // factor)
        
        return f"{int(forecast_qty):,}"

    get_forecast_stock.short_description = "สต็อกคาดการณ์ (ตามหน่วย)"

    @property
    def unit_display(self):
        # ถ้าตัวคูณเป็น 1 หรือไม่ได้ใส่ชื่อหน่วย ให้ถือว่าเป็นหน่วยปกติ
        if self.conversion_factor <= 1 or not self.unit_name:
            return "หน่วยปกติ (ชิ้น)"
        return f"{self.unit_name} ({self.conversion_factor} ชิ้น)"
    
    def __str__(self):
        return self.code
    
    class Meta: verbose_name_plural = "W6. หน่วยขายตามบาร์โค้ด"

# 4.1 คลังสินค้า
class Warehouse(models.Model):
    TYPE_CHOICES = [('normal', 'ปกติ'), ('scrap', 'เศษเสีย')]
    name = models.CharField(max_length=100, unique=True, verbose_name="ชื่อคลัง")
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='normal', verbose_name="ประเภทคลัง")
    is_default = models.BooleanField(
        default=False,
        verbose_name="คลังหลัก (ค่าเริ่มต้น)",
        help_text="สินค้าทุกรายการอยู่คลังนี้เป็นค่าเริ่มต้น (ใช้ค่า stock_quantity เดิมของสินค้าโดยตรง) มีได้คลังเดียวเท่านั้น",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def save(self, *args, **kwargs):
        # คลังหลักมีได้แค่คลังเดียว — ถ้าตั้งคลังนี้เป็นหลัก ให้ปลดคลังอื่นออกอัตโนมัติ
        if self.is_default:
            Warehouse.objects.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "W3. คลังสินค้า (Warehouse)"

# 4.2 สต๊อกแยกคลัง (เฉพาะคลังที่ไม่ใช่คลังหลัก — คลังหลักใช้ Product.stock_quantity ตรงๆ
# เพื่อไม่ต้องแตะจุดคำนวณ/ตัดสต๊อกเดิมของระบบที่ผูกกับ stock_quantity อยู่จำนวนมาก)
class ProductStock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='warehouse_stocks')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='product_stocks')
    quantity = models.IntegerField(default=0, verbose_name="จำนวนคงเหลือ")

    class Meta:
        unique_together = ('product', 'warehouse')
        verbose_name_plural = "สต๊อกแยกคลัง"

    def __str__(self):
        return f"{self.product.name} @ {self.warehouse.name}: {self.quantity}"


def _warehouse_qty(product, warehouse):
    """อ่านจำนวนคงเหลือของสินค้าในคลังที่ระบุ (คลังหลักอ่านจาก Product.stock_quantity ตรงๆ)"""
    if warehouse.is_default:
        return product.stock_quantity or 0
    ps = ProductStock.objects.filter(product=product, warehouse=warehouse).first()
    return ps.quantity if ps else 0


def _warehouse_adjust(product, warehouse, delta):
    """ปรับจำนวนคงเหลือของสินค้าในคลังที่ระบุ (บวก/ลบตาม delta)"""
    if warehouse.is_default:
        Product.objects.filter(pk=product.pk).update(stock_quantity=models.F('stock_quantity') + delta)
    else:
        ps, _created = ProductStock.objects.get_or_create(product=product, warehouse=warehouse)
        ProductStock.objects.filter(pk=ps.pk).update(quantity=models.F('quantity') + delta)

# 4.3 โอนย้ายคลังสินค้า
class StockTransfer(models.Model):
    transfer_number = models.CharField(max_length=50, unique=True, editable=False, verbose_name="เลขที่เอกสาร")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="สินค้า")
    quantity = models.PositiveIntegerField(verbose_name="จำนวน")
    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='transfers_out', verbose_name="คลังต้นทาง")
    to_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='transfers_in', verbose_name="คลังปลายทาง")
    transfer_date = models.DateField(default=datetime.date.today, verbose_name="วันที่โอนย้าย")
    note = models.TextField(blank=True, verbose_name="หมายเหตุ")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_transfers_created")
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def clean(self):
        if self.from_warehouse_id and self.to_warehouse_id and self.from_warehouse_id == self.to_warehouse_id:
            raise ValidationError("คลังต้นทางและคลังปลายทางต้องไม่ใช่คลังเดียวกัน")
        if self.pk is None and self.from_warehouse_id and self.product_id and self.quantity:
            available = _warehouse_qty(self.product, self.from_warehouse)
            if self.quantity > available:
                raise ValidationError(f"คลังต้นทาง \"{self.from_warehouse}\" มีสินค้าคงเหลือ {available} ไม่พอสำหรับโอน {self.quantity}")

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.transfer_number:
            self.transfer_number = generate_number('TR', StockTransfer, 'transfer_number')
        super().save(*args, **kwargs)
        if is_new:
            _warehouse_adjust(self.product, self.from_warehouse, -self.quantity)
            _warehouse_adjust(self.product, self.to_warehouse, self.quantity)

    def delete(self, *args, **kwargs):
        # คืนสต๊อกกลับตำแหน่งเดิมก่อนลบเอกสาร
        _warehouse_adjust(self.product, self.from_warehouse, self.quantity)
        _warehouse_adjust(self.product, self.to_warehouse, -self.quantity)
        return super().delete(*args, **kwargs)

    def __str__(self):
        return self.transfer_number

    class Meta:
        verbose_name_plural = "W4. โอนย้ายคลังสินค้า (Stock Transfer)"

class ProductSupplier(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_suppliers')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, verbose_name="ผู้จำหน่าย")
    supplier_sku = models.CharField(max_length=100, blank=True, verbose_name="รหัสสินค้าฝั่ง Supplier")
    latest_buy_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ทุนล่าสุดจากเจ้านี้")
    class Meta: unique_together = ('product', 'supplier')

    def __str__(self):
        return f"{self.supplier} - {self.product}"

@receiver(post_save, sender=ProductSupplier)
@receiver(post_delete, sender=ProductSupplier)
def recalc_product_cost_on_supplier_change(sender, instance, **kwargs):
    """เมื่อราคาผู้จำหน่าย (ProductSupplier) ถูกแก้ไข/ลบ ไม่ว่าจากหน้าไหน ให้คำนวณต้นทุนสินค้าที่เกี่ยวข้องใหม่"""
    instance.product.recalc_cost_and_price()

# 5. สูตรการผลิต (BOM)
class BOM(models.Model):
    # แก้ไขจาก OneToOneField เป็น ForeignKey และเปลี่ยน related_name เป็นพหูพจน์
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='bom_formulas')
    name = models.CharField(max_length=255, verbose_name="ชื่อสูตร")
    # สูตรเฉพาะลูกค้า: ชื่อสูตรเดียวกันมีได้หลายสูตรถ้าลูกค้าต่างกัน, ว่าง = ทุกลูกค้า (ดู pick_bom)
    customer = models.ForeignKey('Customer', on_delete=models.PROTECT, null=True, blank=True,
                                 related_name='bom_formulas', verbose_name="ลูกค้า",
                                 help_text="ว่าง = ทุกลูกค้า (All) / ระบุ = ใช้สูตรนี้เฉพาะ SO ของลูกค้ารายนี้")
    unit = models.CharField(max_length=50, default="ชิ้น", verbose_name="หน่วยผลิต")
    production_time = models.IntegerField(default=1, verbose_name="เวลาผลิต (วัน)")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="bom_creator")
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="bom_editor")
    @property
    def total_cost(self): return sum(item.subtotal for item in self.ingredients.all())

    def __str__(self):
        try:
            # ดึงชื่อสินค้า และ ชื่อสูตร (บาร์โค้ด) มาโชว์
            p_name = self.product.name if self.product else "ไม่ระบุสินค้า"
            b_name = self.name if self.name else "ไม่มีชื่อสูตร"
            c_name = self.customer.company_name if self.customer_id else "ทุกลูกค้า"
            return f"{p_name} - {b_name} [{c_name}]"
        except Exception:
            return f"BOM ID: {self.id}" # ไม้ตายสุดท้ายถ้าพังจริงๆ ให้โชว์ ID แทน

    def clean(self):
        # ชื่อสูตรซ้ำได้เฉพาะเมื่อลูกค้าต่างกัน (ไม่ใส่เป็น DB constraint เพราะข้อมูลเดิมอาจมีชื่อซ้ำอยู่แล้ว)
        if self.name:
            dup = BOM.objects.filter(name=self.name, customer_id=self.customer_id).exclude(pk=self.pk)
            if dup.exists():
                who = self.customer.company_name if self.customer_id else "ทุกลูกค้า"
                raise ValidationError({'name': f"มีสูตรชื่อ \"{self.name}\" สำหรับ {who} อยู่แล้ว"})

    class Meta: verbose_name_plural = "O1. สูตรการผลิต (BOM)"


def pick_bom(product, barcode=None, customer=None):
    """เลือกสูตรผลิตให้รายการขาย/ใบสั่งผลิต
    สูตรที่ตรงบาร์โค้ด (ชื่อสูตร == รหัสบาร์โค้ด) ก่อน แล้วค่อยสูตรใดๆ ของสินค้า — ในแต่ละชั้น:
    สูตรเฉพาะลูกค้ารายนี้ > สูตรทุกลูกค้า (ไม่ระบุลูกค้า) ไม่ใช้สูตรที่ระบุเป็นของลูกค้ารายอื่นเด็ดขาด"""
    if not product:
        return None
    product_id = getattr(product, 'pk', product)
    customer_id = getattr(customer, 'pk', customer)
    base = BOM.objects.filter(product_id=product_id)
    tiers = []
    code = getattr(barcode, 'code', None)
    if code:
        tiers.append(base.filter(name=code))
    tiers.append(base)
    for qs in tiers:
        if customer_id:
            bom = qs.filter(customer_id=customer_id).order_by('-id').first()
            if bom:
                return bom
        bom = qs.filter(customer__isnull=True).order_by('-id').first()
        if bom:
            return bom
    return None

class BOMIngredient(models.Model):
    bom = models.ForeignKey(BOM, on_delete=models.CASCADE, related_name='ingredients')
    material = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="วัตถุดิบ")
    barcode_obj = models.ForeignKey('ProductBarcode', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="บาร์โค้ด/หน่วยวัตถุดิบ")
    quantity = models.DecimalField(max_digits=10, decimal_places=4, default=1.0000)
    is_scrap = models.BooleanField(
        default=False,
        verbose_name="เศษเสีย",
        help_text="ติ๊กถ้าวัตถุดิบตัวนี้ตอนผลิตจริง นอกจากตัดออกจากคลังหลักตามปกติแล้ว ให้ย้ายเข้าคลังเศษเสียด้วย",
    )

    def clean(self):
        if self.barcode_obj_id and self.material_id and self.barcode_obj.product_id != self.material_id:
            raise ValidationError({
                'barcode_obj': f"❌ บาร์โค้ด '{self.barcode_obj}' ไม่ใช่ของวัตถุดิบ '{self.material}' กรุณาเลือกใหม่"
            })

    @property
    def quantity_base(self):
        """จำนวนที่แปลงเป็นหน่วยหลักของวัตถุดิบแล้ว (ใช้ตัดสต็อกจริง)"""
        factor = self.barcode_obj.conversion_factor if self.barcode_obj else 1
        return self.quantity * factor

    @property
    def subtotal(self): return self.material.buy_price * self.quantity_base
    @property
    def get_unit(self):
        if self.barcode_obj:
            return self.barcode_obj.unit_display
        return self.material.unit if self.material else "-"

@receiver(post_save, sender=BOM)
@receiver(post_delete, sender=BOM)
def recalc_product_cost_on_bom_change(sender, instance, **kwargs):
    """เมื่อสูตร BOM ถูกเพิ่ม/แก้ไข/ลบ ให้คำนวณต้นทุนสินค้าที่ผูกกับสูตรนี้ใหม่ (เทียบ BOM cost กับ Supplier+15%)"""
    instance.product.recalc_cost_and_price()

@receiver(post_save, sender=BOMIngredient)
@receiver(post_delete, sender=BOMIngredient)
def recalc_product_cost_on_bom_ingredient_change(sender, instance, **kwargs):
    """เมื่อรายการวัตถุดิบในสูตร BOM ถูกแก้ไข/ลบ ให้คำนวณต้นทุนของสินค้าที่ใช้สูตรนี้ใหม่"""
    instance.bom.product.recalc_cost_and_price()

# 6. ระบบเอกสารสั่งซื้อ
class PurchaseOrder(models.Model):
    # ✅ 1. รวมญาติสถานะ (Legacy + New)
    # เพื่อให้ข้อมูลเก่าไม่หาย และรองรับระบบใหม่
    STATUS_CHOICES = [
        # --- กลุ่มเริ่มต้น ---
        ('Draft', '⚪ ร่าง (Draft)'),
        ('Pending', '⏳ รอรับของ/สั่งซื้อแล้ว (Pending)'), # (Legacy Default)
        ('Confirmed', '🔵 ยืนยัน (Confirmed)'),
        ('Ordered', '📝 สั่งซื้อแล้ว (Ordered)'),
        
        # --- กลุ่ม Tracking (B4 - ต่างประเทศ) ---
        ('Paid', '💰 จ่ายเงินแล้ว (Paid)'),
        ('Loaded', '📦 ขึ้นตู้แล้ว (Loaded)'),
        ('Departed', '🚢 ออกเดินทาง (Departed)'),
        ('Arrived', '🏁 ถึงไทย (Arrived)'),
        
        # --- กลุ่มรับของ (Warehouse) ---
        ('Received', '📥 รับของบางส่วน (Received)'), # (Legacy)
        ('Partially Received', '📥 รับของบางส่วน (Partial)'), # (New Standard)
        ('Completed', '✅ ปิดงาน/ครบถ้วน (Completed)'),
        
        # --- ยกเลิก ---
        ('Cancelled', '❌ ยกเลิก (Cancelled)'),
    ]

    # ✅ 2. สถานะการเงิน (แยกต่างหาก)
    PAYMENT_STATUS_CHOICES = [
        ('Unpaid', '🔴 ยังไม่จ่าย'),
        ('Partial', '🟠 จ่ายบางส่วน'),
        ('Paid', '🟢 จ่ายครบแล้ว'),
        ('SETTLED', '⚪ ปิดยอดกรณีพิเศษ'),
    ]

    # --- Fields ---
    po_number = models.CharField(max_length=50, unique=True, editable=False)
    supplier = models.ForeignKey('Supplier', on_delete=models.CASCADE)
    invoice_no_supplier = models.CharField(max_length=100, blank=True, verbose_name="เลข Invoice ผู้ขาย")
    order_date = models.DateField(default=datetime.date.today, db_index=True)
    
    # ใช้ max_length=50 เพื่อรองรับทุก key
    status = models.CharField(max_length=50, default='Pending', choices=STATUS_CHOICES, verbose_name="สถานะเอกสาร")
    
    payment_status = models.CharField(max_length=20, default='Unpaid', choices=PAYMENT_STATUS_CHOICES, verbose_name="สถานะการเงิน")

    notes = models.TextField(blank=True, verbose_name="หมายเหตุ")
    vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=7.00, verbose_name="VAT (%)")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    related_po = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Related PO"
    )

    # --- Dates for Tracking ---
    paid_date = models.DateField(null=True, blank=True, verbose_name="วันที่จ่ายเงิน")
    loaded_date = models.DateField(null=True, blank=True, verbose_name="วันที่ขึ้นตู้")
    departed_date = models.DateField(null=True, blank=True, verbose_name="วันที่ออกเดินทาง")
    arrived_date = models.DateField(null=True, blank=True, verbose_name="วันที่ถึงไทย")
    received_date = models.DateField(null=True, blank=True, verbose_name="วันที่ถึงโกดัง (ล่าสุด)")
    cancelled_at = models.DateTimeField(null=True, blank=True, editable=False, verbose_name="วันที่ยกเลิก")

    class Meta:
        verbose_name_plural = "P2. ใบสั่งซื้อ (Purchase)"

    def __str__(self):
        return f"{self.po_number} ({self.get_status_display()})"

    # ==========================================
    # 🧠 PROPERTIES
    # ==========================================
    @property
    def total_items_price(self):
        total = sum(item.quantity_ordered * item.unit_price for item in self.items.all())
        return Decimal(total)

    @property
    def vat_amount(self):
        return self.total_items_price * (self.vat_percent / Decimal(100))

    @property
    def grand_total(self):
        return self.total_items_price + self.vat_amount

    @property
    def total_paid_amount(self):
        return self.payment_logs.aggregate(t=Sum('amount'))['t'] or Decimal(0)

    @property
    def total_paid(self):
        return self.total_paid_amount

    @property
    def balance_due(self):
        return self.grand_total - self.total_paid_amount

    # ==========================================
    # 🚀 LOGIC: UPDATE STATUS
    # ==========================================
    def update_status(self):
        """เรียกเมื่อมีการเปลี่ยนแปลง Receipt Log"""
        total_ordered = self.items.aggregate(t=Sum('quantity_ordered'))['t'] or 0
        # ใช้ยอดสะสมระดับ PurchaseItem (เป็นชิ้นเสมอ) แทนการรวมดิบจาก receipt_logs
        # เพราะ receipt_logs.quantity_received อาจกรอกเป็นหน่วยบาร์โค้ด (เช่น แพ็ค) ไม่ใช่ชิ้น
        total_received = self.items.aggregate(t=Sum('quantity_received'))['t'] or 0

        if total_ordered > 0:
            if total_received >= total_ordered:
                self.status = 'Completed'
                if not self.received_date:
                    self.received_date = datetime.date.today()
            
            elif total_received > 0:
                self.status = 'Partially Received'
                if not self.received_date:
                    self.received_date = datetime.date.today()
            
            else:
                # Fallback: ถ้าลบของออกหมด ให้ถอยสถานะกลับตาม Timeline
                if self.arrived_date: self.status = 'Arrived'
                elif self.departed_date: self.status = 'Departed'
                elif self.loaded_date: self.status = 'Loaded'
                elif self.paid_date: self.status = 'Paid'
                else: self.status = 'Pending' # หรือ Confirmed ตามที่ใช้
                
                self.received_date = None

        self.save(update_fields=['status', 'received_date'])

    def update_payment_status(self):
        paid = self.total_paid_amount
        total = round_money(self.grand_total)
        if total > 0:
            if paid >= total: self.payment_status = 'Paid'
            elif paid > 0: self.payment_status = 'Partial'
            else: self.payment_status = 'Unpaid'
        self.save(update_fields=['payment_status'])

    # ==========================================
    # 💾 SAVE & DELETE (Safety First)
    # ==========================================
    def save(self, *args, **kwargs):
        # 1. รันเลข PO
        if not self.po_number:
            try:
                self.po_number = generate_number('PO', PurchaseOrder, 'po_number')
            except:
                pass 

        # 2. Logic ต่างประเทศ (VAT 0)
        if self.supplier_id:
            if hasattr(self.supplier, 'type') and self.supplier.type == 'International':
                self.vat_percent = Decimal(0)

        # 3. บันทึกวันที่ยกเลิก (สำหรับหน้าประวัติสินค้า)
        if self.status == 'Cancelled':
            if not self.cancelled_at:
                self.cancelled_at = timezone.now()
        else:
            self.cancelled_at = None

        super().save(*args, **kwargs)

class PurchaseItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    barcode_obj = models.ForeignKey('ProductBarcode', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="บาร์โค้ด/หน่วยสั่งซื้อ")
    quantity_unit = models.PositiveIntegerField(default=1, verbose_name="จำนวนที่สั่ง (ตามหน่วย)")
    quantity_ordered = models.PositiveIntegerField(verbose_name="จำนวนรวม (ชิ้น)")
    quantity_received = models.PositiveIntegerField(default=0, verbose_name="รับสะสม")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ราคา/หน่วย")
    
    @property
    def total_paid(self):
        # ✅ ในเมื่อไม่มี related_name ต้องใช้ชื่อคลาสตัวเล็กตามด้วย _set
        # และเช็คว่าใน PurchasePaymentLog เปรมใช้ฟิลด์เงินชื่อ 'amount' หรือเปล่านะคะ
        if hasattr(self, 'purchasepaymentlog_set'):
            return sum(log.amount for log in self.purchasepaymentlog_set.all())
        return 0

    @property
    def total_price(self):
        # ✅ เช็คก่อนว่ามีค่าครบทั้งคู่ไหม ถ้าไม่มีให้คืนค่า 0 ไปก่อน
        if self.quantity_ordered is None or self.unit_price is None:
            return 0
        return self.quantity_ordered * self.unit_price

    def save(self, *args, **kwargs):
        # 🎯 ถ้าเลือกบาร์โค้ด: ดึงสินค้าจากบาร์โค้ด + แปลงจำนวนเป็นหน่วยหลัก (ชิ้น)
        # unit_price ไม่แปลง เพราะเป็นราคาต่อชิ้น (หน่วยหลัก) เสมอ ไม่ใช่ราคาต่อหน่วยบาร์โค้ด
        if self.barcode_obj_id:
            self.product = self.barcode_obj.product
            factor = getattr(self.barcode_obj, 'conversion_factor', 1) or 1
            self.quantity_ordered = self.quantity_unit * factor
        else:
            self.quantity_ordered = self.quantity_unit

        # 🔥 Logic: ถ้าไม่ได้ระบุราคา (ใส่ 0) ให้วิ่งไปดูราคาทุนจาก Supplier
        if self.unit_price == 0:
            try:
                # ค้นหาว่า Supplier เจ้านี้ ขายสินค้านี้ราคาเท่าไหร่
                match = ProductSupplier.objects.filter(
                    supplier=self.purchase_order.supplier,
                    product=self.product
                ).first()
                
                if match and match.latest_buy_price > 0:
                    self.unit_price = match.latest_buy_price # เจอ! ใช้ราคาจาก Supplier
                else:
                    self.unit_price = self.product.buy_price # ไม่เจอ ใช้ราคากลาง
            except:
                pass
        super().save(*args, **kwargs)
        
# ✅ 3. เพิ่ม Class ใหม่: PurchasePaymentLog (บันทึกการจ่ายเงิน)
# (วางต่อท้าย PurchaseItem ได้เลยครับ)

class PurchasePaymentLog(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='payment_logs')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="ยอดที่จ่าย")
    payment_date = models.DateField(default=datetime.date.today, verbose_name="วันที่จ่าย")
    notes = models.CharField(max_length=200, blank=True, verbose_name="หมายเหตุ/เลขที่สลิป")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="ผู้บันทึก")
    bank_account = models.ForeignKey('BankAccount', on_delete=models.PROTECT, null=True, blank=True,
                                     related_name='+', verbose_name="สมุดบัญชี")

    def __str__(self): return f"{self.amount}"

class PurchaseReceiptLog(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='receipt_logs')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="สินค้าที่รับ")
    barcode_obj = models.ForeignKey('ProductBarcode', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="บาร์โค้ด/หน่วยที่รับ")
    quantity_received = models.PositiveIntegerField(verbose_name="จำนวนที่รับครั้งนี้ (ตามหน่วยที่เลือก)")
    supplier_invoice = models.CharField(max_length=100, blank=True, verbose_name="เลข Invoice/ใบส่งของ Supplier")
    notes = models.TextField(blank=True, verbose_name="หมายเหตุ")
    received_date = models.DateTimeField(auto_now_add=True, verbose_name="วันเวลาที่บันทึก")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="ผู้บันทึก")
    def save(self, *args, **kwargs):
        if self.barcode_obj_id and not self.product_id:
            self.product = self.barcode_obj.product

        # factor = จำนวนชิ้นต่อหน่วยบาร์โค้ด (เช่น แพ็ค=6, ชิ้น=1)
        factor = getattr(self.barcode_obj, 'conversion_factor', 1) or 1

        is_new = self.pk is None
        if is_new:
            diff = self.quantity_received
        else:
            old_qty = PurchaseReceiptLog.objects.values_list('quantity_received', flat=True).get(pk=self.pk)
            diff = self.quantity_received - old_qty

        if diff != 0:
            diff_pieces = diff * factor
            self.product.stock_quantity += diff_pieces
            self.product.save(update_fields=['stock_quantity'])
            item = PurchaseItem.objects.get(purchase_order=self.purchase_order, product=self.product)
            item.quantity_received += diff_pieces  # สะสมเป็นชิ้นเสมอ ให้ตรงกับ quantity_ordered
            item.save(update_fields=['quantity_received'])

        super().save(*args, **kwargs)
        self.purchase_order.update_status()

# --- ย้ายออกมานอก Class และจัดแนวแถวให้ตรงกัน ---
@receiver(post_delete, sender=PurchaseReceiptLog)
def handle_receipt_deletion(sender, instance, **kwargs):
    factor = getattr(instance.barcode_obj, 'conversion_factor', 1) or 1
    qty_pieces = instance.quantity_received * factor

    instance.product.stock_quantity -= qty_pieces
    instance.product.save()
    try:
        item = PurchaseItem.objects.get(purchase_order=instance.purchase_order, product=instance.product)
        item.quantity_received -= qty_pieces
        item.save()
    except:
        pass
    instance.purchase_order.update_status()

# 7. ระบบเอกสารสั่งขาย
class SalesOrder(models.Model):
    STATUS_CHOICES = [('Draft','ร่าง'),('Confirmed','ยืนยัน'),('Shipped','ส่งบางส่วน'),('Completed','ปิดงาน/ครบถ้วน'),('Cancelled','ยกเลิก')]
    so_number = models.CharField(max_length=50, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    po_no_customer = models.CharField(max_length=100, blank=True, verbose_name="เลข PO ลูกค้า")
    vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=7.00, verbose_name="VAT (%)") 
    order_date = models.DateField(default=datetime.date.today,db_index=True)
    status = models.CharField(max_length=20, default='Draft', choices=STATUS_CHOICES)
    notes = models.TextField(blank=True, verbose_name="หมายเหตุ")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True, editable=False, verbose_name="วันที่ยกเลิก")

    @property
    def total_items_price(self):
        # ✅ ตอนนี้เรียก item.total_price ได้แล้ว เพราะเราสร้างไว้ข้างบน
        return sum(item.total_price for item in self.items.all())

    @property
    def vat_amount(self):
        return (self.total_items_price * self.vat_percent) / 100

    @property
    def grand_total(self):
        return self.total_items_price + self.vat_amount

    @property
    def credited_total(self):
        # ยอดใบลดหนี้ (รวม VAT) ของใบสั่งขายนี้ — หักออกจากยอดที่ต้องเก็บเงิน
        if not self.pk:
            return Decimal('0')
        return self.credit_notes.aggregate(t=Sum('grand_total'))['t'] or Decimal('0')

    @property
    def balance_due(self):
        # ยอดค้างรับ = ยอดสุทธิ - ใบลดหนี้ - ยอดที่รับเงินมาแล้ว
        total_paid = sum(p.amount for p in self.payments.all()) if hasattr(self, 'payments') else 0
        return self.grand_total - self.credited_total - total_paid
    
    def __str__(self):
        return self.so_number
    
    def update_status(self):
        """เรียกเมื่อมีการเปลี่ยนแปลง DeliveryLog"""
        if self.status in ('Completed', 'Cancelled'):
            return
        total_ordered = self.items.aggregate(t=Sum('quantity_ordered'))['t'] or 0
        total_shipped = self.items.aggregate(t=Sum('quantity_shipped'))['t'] or 0

        if total_ordered > 0 and total_shipped >= total_ordered:
            self.status = 'Completed'
        elif total_shipped > 0:
            self.status = 'Shipped'
        else:
            self.status = 'Confirmed'
        self.save(update_fields=['status'])

    def save(self, *args, **kwargs):
        if not self.so_number: self.so_number = generate_number('SO', SalesOrder, 'so_number')
        # บันทึกวันที่ยกเลิก (สำหรับหน้าประวัติสินค้า)
        if self.status == 'Cancelled':
            if not self.cancelled_at:
                self.cancelled_at = timezone.now()
        else:
            self.cancelled_at = None
        super().save(*args, **kwargs)

    class Meta: verbose_name_plural = "S2. ใบสั่งขาย (Sales)"

    # ✅ เพิ่มสถานะการเงิน
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('Unpaid', '🔴 ยังไม่รับเงิน'),
            ('Partial', '🟠 รับเงินบางส่วน'),
            ('Paid', '🟢 รับเงินครบแล้ว'),
            ('SETTLED', '⚪ ปิดยอดกรณีพิเศษ'),
        ],
        default='Unpaid',
        verbose_name="สถานะการรับเงิน"
    )

    # ✅ แก้ฟังก์ชันคำนวณ
    def update_payment_status(self):
        total_received = self.payments.aggregate(Sum('amount'))['amount__sum'] or Decimal(0)
        
        if total_received >= round_money(self.grand_total - self.credited_total):
            self.payment_status = 'Paid'
        elif total_received > 0:
            self.payment_status = 'Partial'
        else:
            self.payment_status = 'Unpaid'
            
        self.save(update_fields=['payment_status'])
        
    def get_balance_due_display(self):
        # ทำให้ออกมาเป็นตัวอักษรพร้อมคอมม่าและทศนิยม 2 ตำแหน่ง
        return f"{self.balance_due:,.2f} บาท"

# --- 3. ตารางประวัติการรับเงิน (SalesPayment) ---
class SalesPayment(models.Model):
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateField(default=datetime.date.today, verbose_name="วันที่รับเงิน")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ยอดเงินที่รับ")
    remark = models.CharField(max_length=200, blank=True, null=True, verbose_name="หมายเหตุ")
    evidence = models.ImageField(upload_to='payment_evidence/', blank=True, null=True, verbose_name="หลักฐานการโอน")
    bank_account = models.ForeignKey('BankAccount', on_delete=models.PROTECT, null=True, blank=True,
                                     related_name='+', verbose_name="สมุดบัญชี")
    # แถวที่ action "ขายแฟคตอริ่ง" สร้าง: ADVANCE = เบิกล่วงหน้า, REMAINDER = ส่วนที่เหลือตอนลูกค้าจ่าย
    FACTORING_ROLES = [('ADVANCE', 'เบิกล่วงหน้า'), ('REMAINDER', 'ส่วนที่เหลือ')]
    factoring_role = models.CharField(max_length=10, choices=FACTORING_ROLES, blank=True, default='',
                                      editable=False, verbose_name="แฟคตอริ่ง")
    # เก็บไว้ที่แถว REMAINDER: วันที่ลูกค้าจ่าย (จบการคิดดอกเบี้ย) + อัตราดอกเบี้ย ณ วันที่ทำรายการ
    factoring_customer_paid_date = models.DateField(null=True, blank=True, editable=False)
    factoring_rate = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True, editable=False)
    # รายการหัก DC/Rebate ที่สร้างจาก A5 (1 แถวต่อรายการส่งของ + ประเภท) และรอบเดือนที่เลือกให้หัก
    DEDUCTION_KINDS = [('DC', 'DC'), ('REBATE', 'Rebate')]
    deduction_log = models.ForeignKey('SalesDeliveryLog', on_delete=models.CASCADE, null=True, blank=True,
                                      related_name='deductions', editable=False)
    deduction_kind = models.CharField(max_length=10, choices=DEDUCTION_KINDS, blank=True, default='',
                                      editable=False, verbose_name="หัก")
    deduct_month = models.DateField(null=True, blank=True, editable=False, db_index=True,
                                    verbose_name="หักรอบเดือน")

    def __str__(self):
        return f"รับเงิน {self.amount:,.2f}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # บันทึกเสร็จ ให้ไปอัปเดตสถานะที่ใบสั่งขายทันที
        self.order.update_payment_status()

#ดักจับ ถ้ามีการ ลบประวัติการรับเงินออก ให้ไปอัปเดตสถานะที่ใบสั่งขาย และสถานะใน C6 ด้วยเช่นกัน
@receiver(post_delete, sender=SalesPayment)
def unlock_shipment_accounting(sender, instance, **kwargs):
    """
    เมื่อมีการลบประวัติการรับเงิน/หักออก (SalesPayment)
    ระบบจะพยายามปลดล็อกสถานะใน C6 (ShipmentAccounting) ให้อัตโนมัติ
    """
    remark = instance.remark or ""
    # 🔍 ค้นหา ID อ้างอิงจาก Remark
    match = re.search(r"\[REF-ID:(\d+)\]", remark)
    if match:
        shipment_id = match.group(1)
        try:
            # ดึงรายการ Shipment ต้นทางขึ้นมา
            ship = ShipmentAccounting.objects.get(id=shipment_id)
            
            # เช็คว่ารายการที่ลบคืออะไร แล้วปลดล็อกตัวนั้น
            if "ยอดส่งสินค้า" in remark:
                ship.is_revenue_confirmed = False
            elif "DC" in remark:
                ship.is_dc_confirmed = False
            elif "Rebate" in remark:
                ship.is_rebate_confirmed = False
                
            ship.save() # บันทึกเพื่อให้หน้า C6 กลับเป็นสีแดง
        except Exception:
            pass
    order = instance.order
    if "สินค้า" in remark or "หัก" in remark:
        from .models import SalesDeliveryLog
        shipments = SalesDeliveryLog.objects.filter(sales_order=order)
        
        for ship in shipments:
            if "DC" in remark and ship.is_dc_confirmed:
                if abs(ship.dc_amount) == abs(instance.amount):
                    ship.is_dc_confirmed = False
                    ship.save()
                    break
            elif "Rebate" in remark and ship.is_rebate_confirmed:
                if abs(ship.rebate_amount) == abs(instance.amount):
                    ship.is_rebate_confirmed = False
                    ship.save()
                    break

# --- 4. Proxy Model สำหรับหน้า C3 (Income Report) ---
class IncomeReport(SalesOrder):
    class Meta:
        proxy = True
        verbose_name = "A4. สรุปรายรับ (SO Report)"
        verbose_name_plural = "A4. สรุปรายรับ (SO Report)"

    @property
    def grand_total(self):
        # 1. หายอดรวมสินค้าทั้งหมด (Subtotal)
        subtotal = sum(item.total_price for item in self.items.all()) if hasattr(self, 'items') else 0
        # 2. ดึงค่า % VAT มาจากฟิลด์ (ถ้าไม่มีหรือเป็น None ให้เป็น 0)
        vat_p = getattr(self, 'vat_percent', 0) or 0
        # 3. คำนวณยอดรวมสุทธิที่รวมภาษีแล้ว
        total_with_vat = subtotal + (subtotal * vat_p / 100)
        
        return total_with_vat

    @property
    def total_paid(self):
        # คำนวณยอดที่รับชำระมาแล้ว (สมมติว่ามี Model เก็บการรับเงิน)
        total = sum(p.amount for p in self.payments.all()) if hasattr(self, 'payments') else 0
        return total

    @property
    def balance_due(self):
        # ยอดค้างรับ = ยอดรวมสุทธิ - ใบลดหนี้ - ยอดที่จ่ายแล้ว
        return self.grand_total - self.credited_total - self.total_paid

class SalesItem(models.Model):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='sales_items', # ห้ามลบตัวนี้เด็ดขาด!
        null=True,   
        blank=True   
    )
    quantity_shipped = models.PositiveIntegerField(default=0, verbose_name="ส่งสะสม")
    bom = models.ForeignKey(
        'BOM', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="สูตรผลิต"
    )
    barcode_obj = models.ForeignKey(ProductBarcode, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="บาร์โค้ด/หน่วยขาย")
    # ช่องคีย์หลัก (คีย์ได้ทั้ง 10 ชิ้น หรือ 10 แพ็ค)
    quantity_unit = models.PositiveIntegerField(default=1, verbose_name="จำนวนที่สั่ง")
    # ช่องผลลัพธ์ (Readonly ใน Admin) สำหรับ Pending Out
    quantity_ordered = models.PositiveIntegerField(default=0, verbose_name="จำนวนรวม (ชิ้น)")

    # ✅ เพิ่ม 2 ฟิลด์นี้เพื่อทำ auto production ค่ะ
    auto_produce = models.BooleanField(default=False, verbose_name="ผลิตทันที (Auto PD)")
    is_produced = models.BooleanField(default=False, editable=False) # เก็บไว้หลังบ้านกันสร้างซ้ำ

# ✅ 1. เพิ่มฟิลด์จริงลงฐานข้อมูล (เพื่อใช้เก็บราคาที่อาจจะโดนแก้ไข)
    sale_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00, 
        verbose_name="ราคาขาย"
    )

    quantity_shipped = models.PositiveIntegerField(default=0, verbose_name="ส่งสะสม")
    auto_produce = models.BooleanField(default=False, verbose_name="ผลิตทันที (Auto PD)")
    is_produced = models.BooleanField(default=False, editable=False)

    @property
    def total_price(self):
        """
        ใช้สำหรับแสดงผลราคารวมในหน้า Admin 
        โดยไล่ลำดับ: ราคาที่ระบุเอง > ราคาสัญญา > ราคามาตรฐาน
        """
        # 1. เช็คราคาจากฟิลด์ตัวเองก่อน
        price = self.sale_price
        
        # 2. ถ้าเป็น 0 หรือไม่ได้ระบุ ให้ลองหา 'ราคาสัญญา' หรือ 'ราคามาตรฐาน' มาโชว์เผื่อไว้
        if not price or price <= 0:
            from .models import CustomerProductContract
            contract = CustomerProductContract.objects.filter(
                customer=self.sales_order.customer,
                product=self.product
            ).first()
            
            if contract:
                price = contract.contract_price
            else:
                price = self.product.sale_price if self.product else 0
        
        qty = self.quantity_ordered or 0
        return price * qty

    def save(self, *args, **kwargs):
        # 🎯 ขั้นที่ 1: จัดการข้อมูลสินค้าและจำนวน (Priority: Barcode > Product)
        if self.barcode_obj:
            # ดึงสินค้าจากบาร์โค้ดมาใส่ในช่อง product ทันที
            self.product = self.barcode_obj.product
            
            # คำนวณจำนวนตามตัวคูณ
            factor = getattr(self.barcode_obj, 'conversion_factor', 1) or 1
            self.quantity_ordered = self.quantity_unit * factor
            
            # เลือก BOM ตามบาร์โค้ด + ลูกค้าของ SO (ถ้าว่าง)
            if not self.bom:
                self.bom = pick_bom(self.product, self.barcode_obj, self.sales_order.customer_id)
        else:
            # กรณีไม่มีบาร์โค้ด (เลือกสินค้าเอง)
            self.quantity_ordered = self.quantity_unit
            # สูตรของลูกค้ารายนี้ > สูตรทุกลูกค้า (ล่าสุด)
            if self.product and not self.bom:
                self.bom = pick_bom(self.product, None, self.sales_order.customer_id)

        # 🎯 ขั้นที่ 2: จัดการเรื่องราคา (ดึงจากสัญญา T2.1)
        # เช็คว่ามี product หรือยัง (ป้องกันพังถ้ากรอกไม่ครบ)
        if self.product and (not self.sale_price or self.sale_price == 0):
            from .models import CustomerProductContract
            
            contract = CustomerProductContract.objects.filter(
                customer=self.sales_order.customer,
                product=self.product
            ).first()

            # ราคาต่อชิ้น (Contract หรือ Standard)
            base_unit_price = contract.contract_price if contract else (self.product.sale_price or 0)
            
            # คำนวณราคาตามหน่วยที่ขาย
            factor = self.barcode_obj.conversion_factor if self.barcode_obj else 1
            self.sale_price = base_unit_price * factor
        
        # 🎯 ขั้นสุดท้าย: บันทึกข้อมูล
        super().save(*args, **kwargs)

class SalesDeliveryLog(models.Model):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='delivery_logs')
    barcode_obj = models.ForeignKey('ProductBarcode', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="บาร์โค้ด/แพ็คเกจ")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="สินค้าที่ส่ง")
    # ติดลบได้เฉพาะแถว "รับคืนจากใบลดหนี้" (credit_note_item) — แถวส่งของปกติเป็นบวกเสมอ
    quantity_shipped = models.IntegerField(verbose_name="จำนวน")
    shipping_no = models.CharField(max_length=100, blank=True, verbose_name="เลขใบขนส่ง/MB Invoice")
    notes = models.TextField(blank=True, verbose_name="หมายเหตุ")
    shipped_date = models.DateTimeField(
        default=timezone.now, db_index=True,
        verbose_name="วันที่ส่งของ"
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="ผู้บันทึก")
    dc_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="ยอดหัก DC")
    rebate_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="ยอดหัก Rebate")
    shipment_value = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="ยอดรวมสินค้า (ก่อนหัก)")
    payment_due_date = models.DateField(blank=True, null=True, verbose_name="วันกำหนดรับเงิน")
    is_barcode_locked = models.BooleanField(default=False, verbose_name='ล็อค')
    is_revenue_confirmed = models.BooleanField(default=False, verbose_name="Paid")
    is_dc_confirmed = models.BooleanField(default=False, verbose_name="DC")
    is_rebate_confirmed = models.BooleanField(default=False, verbose_name="Rebate")
    confirmed_date = models.DateTimeField(null=True, blank=True)
    # 🎯 ฟิลด์อ้างอิงการจ่ายเงิน (ถ้ามี)
    payment_note = models.CharField(max_length=255, blank=True, verbose_name="หมายเหตุการจ่าย")
    # แถวที่เกิดจากใบลดหนี้ (รับคืน/ลดยอด) — จำนวน/มูลค่าติดลบ ให้สต็อก DC/Rebate/ยอดสัญญา ลดตามอัตโนมัติ
    # แต่ไม่นับเป็น "การส่งของ" (ไม่แตะยอดส่งสะสมของใบสั่งขาย ไม่ออกใบ IV ไม่โชว์ในแผงส่งของ)
    credit_note_item = models.OneToOneField(
        'CreditNoteItem', null=True, blank=True, on_delete=models.CASCADE,
        related_name='delivery_log', editable=False, verbose_name="ใบลดหนี้")

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        # auto-derive product from barcode
        if self.barcode_obj_id and not self.product_id:
            self.product = self.barcode_obj.product

        # factor = จำนวนชิ้นต่อหน่วยบาร์โค้ด (เช่น โหล=12, ชิ้น=1)
        factor = getattr(self.barcode_obj, 'conversion_factor', 1) or 1

        # ผลต่างจำนวนที่ส่ง — รองรับทั้งสร้างแถวใหม่และแก้ไขแถวเดิม (ก่อนหน้านี้ทำงานแค่ตอนสร้างใหม่
        # ทำให้แก้จำนวนในแถวเดิมแล้วสต็อก/ยอดสะสม/สถานะใบไม่อัพเดทตาม)
        if is_new:
            diff = self.quantity_shipped
            shipped_date_changed = True
        else:
            old_qty, old_shipped_date = SalesDeliveryLog.objects.values_list(
                'quantity_shipped', 'shipped_date'
            ).get(pk=self.pk)
            diff = self.quantity_shipped - old_qty
            shipped_date_changed = old_shipped_date != self.shipped_date

        # --- 🚀 [LOGIC เดิมของเปรม] ---
        # 1. สมองกล: ปรับสต็อกจริงตามผลต่าง (เป็นชิ้น)
        if diff != 0:
            qty_pieces = diff * factor
            self.product.stock_quantity -= qty_pieces
            self.product.save()

        # 2. สมองกล: สะสมยอดส่งในใบ SO ตามผลต่าง
        # quantity_shipped ใน SalesItem ต้องเป็น "ชิ้น" เสมอ ให้ตรงกับ quantity_ordered
        # (เดิมสะสมเป็นหน่วยบาร์โค้ดดิบๆ ทำให้ยอดค้างส่ง/สต็อกคาดการณ์ผิดเมื่อ factor != 1 — แก้แล้ว)
        qs = SalesItem.objects.filter(sales_order=self.sales_order, product=self.product)
        if self.barcode_obj_id:
            item = qs.filter(barcode_obj=self.barcode_obj).first() or qs.first()
        else:
            item = qs.first()
        if item and diff != 0 and not self.credit_note_item_id:
            item.quantity_shipped += diff * factor  # ชิ้น
            item.save()
        # --- 🛑 [จบ LOGIC เดิม] ---

        # --- 2. [คำนวณเงินแยกถัง — คำนวณใหม่ทุกครั้งให้ตรงกับ quantity_shipped ปัจจุบันเสมอ] ---
        if item:
            # sale_price คือราคาต่อหน่วยบาร์โค้ด (โหล/ชิ้น) × จำนวนที่ส่ง (หน่วยบาร์โค้ด)
            self.shipment_value = item.sale_price * self.quantity_shipped
            self.sync_dc_rebate_from_contract()

        # --- 3. [คำนวณวันจ่ายเงินตามรอบบัญชี — อิงจาก "วันที่ส่งของจริง" (shipped_date) เสมอ
        # ไม่ใช่วันที่กดบันทึก เพราะลูกค้านับเครดิตจากวันที่ได้รับของจริง — คำนวณใหม่ทุกครั้งที่
        # shipped_date เปลี่ยน (ไม่ใช่แค่ตอนสร้างแถวใหม่) เผื่อแก้วันที่ย้อนหลัง (ดู
        # SalesOrderAdmin.ship_batch_view → edit_batch_date) ---
        if (is_new or shipped_date_changed) and self.sales_order.customer:
            close_day = self.sales_order.customer.account_close_day
            term = self.sales_order.customer.payment_term
            ref_date = self.shipped_date.date() if hasattr(self.shipped_date, 'date') else self.shipped_date

            try:
                current_closing = ref_date.replace(day=close_day)
            except ValueError:
                next_month = ref_date.replace(day=28) + datetime.timedelta(days=4)
                current_closing = next_month - datetime.timedelta(days=next_month.day)

            if ref_date > current_closing:
                first_of_next = (current_closing.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
                try:
                    base_date = first_of_next.replace(day=close_day)
                except ValueError:
                    next_next = first_of_next.replace(day=28) + datetime.timedelta(days=4)
                    base_date = next_next - datetime.timedelta(days=next_next.day)
            else:
                base_date = current_closing

            self.payment_due_date = base_date + datetime.timedelta(days=term)

        # บันทึกลงฐานข้อมูลจริง
        super().save(*args, **kwargs)
        self.sales_order.update_status()

    @property
    def total_with_vat(self):
        # ยอดรับเงินจริง = (ยอดสินค้า - ยอดหัก DC - ยอดหัก Rebate) + VAT
        net_before_vat = self.shipment_value - self.dc_amount - self.rebate_amount
        vat_p = self.sales_order.vat_percent or 0
        return net_before_vat * (1 + (vat_p / 100))

    def sync_dc_rebate_from_contract(self):
        """ดึงข้อมูล DC/Rebate จากสัญญา (T2 Price List) ปัจจุบันมาคำนวณแยกเก็บเป็น "บาท"
        ไว้ในคอลัมน์ dc_amount/rebate_amount ของแถวนี้ (ไม่ save)"""
        from .models import CustomerProductContract
        contract = CustomerProductContract.objects.filter(
            customer=self.sales_order.customer,
            product=self.product
        ).first()

        if contract:
            self.dc_amount = self.shipment_value * (contract.dc_percent / 100)
            self.rebate_amount = self.shipment_value * (contract.rebate_percent / 100)
        else:
            self.dc_amount = 0
            self.rebate_amount = 0

@receiver(post_delete, sender=SalesDeliveryLog)
def handle_delivery_deletion(sender, instance, **kwargs):
    factor = getattr(instance.barcode_obj, 'conversion_factor', 1) or 1
    qty_pieces = instance.quantity_shipped * factor

    # 1. คืนสต็อกสินค้า (เป็นชิ้น)
    if instance.product_id:
        try:
            instance.product.stock_quantity += qty_pieces
            instance.product.save()
        except Exception:
            pass
    if instance.credit_note_item_id:
        # แถวรับคืนจากใบลดหนี้ ไม่ได้นับเป็นยอดส่ง — คืนแค่สต็อกด้านบนพอ
        return

    # 2. หักยอดส่งสะสมใน SO (เป็นชิ้นเสมอ ให้ตรงกับ quantity_ordered)
    try:
        qs = SalesItem.objects.filter(sales_order=instance.sales_order, product=instance.product)
        if instance.barcode_obj_id:
            item = qs.filter(barcode_obj=instance.barcode_obj).first() or qs.first()
        else:
            item = qs.first()
        if item:
            item.quantity_shipped -= qty_pieces  # ชิ้น
            item.save()
    except Exception:
        pass
    
    # 🤖 ออโต้สถานะ
    so = instance.sales_order
    so.status = 'Shipped' if so.status == 'Completed' else so.status
    so.save(update_fields=['status'])
    so.update_status()


# ── ใบเสร็จรับเงิน (IV) ───────────────────────────────────────────────────────
# 1 รอบส่งของ (SalesOrder + วันที่ส่ง) = ใบเสร็จรับเงิน 1 ใบ สร้าง/อัปเดต/ลบอัตโนมัติ
# ผ่าน signal ของ SalesDeliveryLog — ผู้ใช้แก้ได้เฉพาะ "หมายเหตุ" กับ "วันครบกำหนด"
# เลขที่: ใช้ generate_number() ตัวเดียวกับ SO/PO ทุกอย่าง เปลี่ยนแค่ prefix เป็น IV
# => รูปแบบ IV-YYYYMM-0001
class SalesReceipt(models.Model):
    receipt_number = models.CharField(max_length=50, unique=True, editable=False, verbose_name="เลขที่ใบเสร็จ")
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='receipts', editable=False, verbose_name="ใบสั่งขายอ้างอิง")
    shipped_date = models.DateField(db_index=True, editable=False, verbose_name="วันที่")
    due_date = models.DateField(null=True, blank=True, verbose_name="วันครบกำหนด")
    notes = models.TextField(blank=True, verbose_name="หมายเหตุ")
    # ยอดเงิน cache ไว้ในแถว — หน้า list/Export ไม่ต้อง aggregate ใหม่ทีละแถว (กัน N+1)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False, verbose_name="รวมเป็นเงิน")
    vat_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False, verbose_name="ภาษีมูลค่าเพิ่ม")
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False, verbose_name="ยอดรวมสุทธิ")
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    # รอบส่งของถูกลบ/เปลี่ยนวันที่ -> ไม่ลบใบทิ้ง แต่ทำเครื่องหมายยกเลิก (เลขที่ยังอยู่ในทะเบียน/รายงานภาษีขาย
    # และไม่ถูกนำกลับมาใช้ซ้ำ) — 1 ใบสั่งขาย + 1 วัน มีใบที่ "ยังไม่ยกเลิก" ได้แค่ 1 ใบ
    is_cancelled = models.BooleanField(default=False, editable=False, db_index=True, verbose_name="ยกเลิก")
    cancelled_at = models.DateTimeField(null=True, blank=True, editable=False, verbose_name="วันที่ยกเลิก")

    class Meta:
        verbose_name = "ใบเสร็จรับเงิน"
        verbose_name_plural = "A1. ใบเสร็จรับเงิน (Receipt)"
        ordering = ('-shipped_date', '-id')

    def __str__(self):
        return self.receipt_number

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = generate_number('IV', SalesReceipt, 'receipt_number')
        super().save(*args, **kwargs)


# ── ใบกำกับภาษี/ใบส่งของ ──────────────────────────────────────────────────────
# เป็น "มุมมอง/เมนูแยก" ของ SalesReceipt — แถวเดียวกัน เลขที่เดียวกัน (IV-YYYYMM-####)
# 1 รอบส่งของ = 1 ใบ, sync อัตโนมัติผ่าน signal ของ SalesDeliveryLog ตัวเดียวกับใบเสร็จ
# ต่างกันแค่หน้าพิมพ์ (เลย์เอาต์ใบส่งของ/ใบกำกับภาษี แทนใบเสร็จรับเงิน)
class SalesInvoice(SalesReceipt):
    class Meta:
        proxy = True
        verbose_name = "ใบกำกับภาษี/ใบส่งของ"
        verbose_name_plural = "A2. ใบกำกับภาษี/ใบส่งของ (Invoice)"


# ── ใบลดหนี้ (CN) ─────────────────────────────────────────────────────────────
# ลดหนี้อ้างอิงใบกำกับภาษี/ใบส่งของ (IV) 1 ใบ — แต่ละรายการสร้าง SalesDeliveryLog จำนวนติดลบ 1 แถว (credit_note_item)
# เพื่อให้ สต็อก / DC / Rebate / ยอดสัญญา / รายงานที่รวมจาก log ลดตามเองทั้งหมด
# ยอด (รวม VAT) หักออกจากยอดค้างรับของใบสั่งขาย (SalesOrder.credited_total)
class CreditNote(models.Model):
    cn_number = models.CharField(max_length=50, unique=True, editable=False, verbose_name="เลขที่ใบลดหนี้")
    receipt = models.ForeignKey('SalesReceipt', on_delete=models.PROTECT, null=True, related_name='credit_notes',
                                verbose_name="ใบกำกับภาษี/ใบส่งของ")
    # ตั้งจากใบกำกับอัตโนมัติ (ใช้หักยอดค้างรับของใบสั่งขาย)
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, related_name='credit_notes',
                                    editable=False, verbose_name="ใบสั่งขาย")
    doc_date = models.DateField(default=datetime.date.today, db_index=True, verbose_name="วันที่")
    reason = models.CharField(max_length=255, blank=True, verbose_name="สาเหตุการลดหนี้")
    notes = models.TextField(blank=True, verbose_name="หมายเหตุ")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False, verbose_name="มูลค่า")
    vat_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False, verbose_name="ภาษีมูลค่าเพิ่ม")
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False, verbose_name="รวม")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="ผู้บันทึก")
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        verbose_name = "ใบลดหนี้"
        verbose_name_plural = "A8. ใบลดหนี้ (Credit Note)"
        ordering = ('-doc_date', '-id')

    def __str__(self):
        return self.cn_number

    def save(self, *args, **kwargs):
        if not self.cn_number:
            self.cn_number = generate_number('CN', CreditNote, 'cn_number')
        if self.receipt_id:
            self.sales_order_id = self.receipt.sales_order_id
        super().save(*args, **kwargs)

    def recalc_totals(self):
        subtotal = self.items.aggregate(t=Sum('amount'))['t'] or Decimal('0')
        vat_p = self.sales_order.vat_percent or Decimal('0')
        vat_amount = (subtotal * vat_p / Decimal('100')).quantize(Decimal('0.01'))
        self.subtotal, self.vat_amount, self.grand_total = subtotal, vat_amount, subtotal + vat_amount
        self.save(update_fields=['subtotal', 'vat_amount', 'grand_total'])
        self.sales_order.update_payment_status()


class CreditNoteItem(models.Model):
    credit_note = models.ForeignKey(CreditNote, on_delete=models.CASCADE, related_name='items')
    sales_item = models.ForeignKey('SalesItem', on_delete=models.PROTECT, related_name='credit_note_items', verbose_name="รายการในใบสั่งขาย")
    quantity = models.PositiveIntegerField(verbose_name="จำนวนลดหนี้")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="ราคา/หน่วย")
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name="มูลค่า")

    class Meta:
        verbose_name = "รายการลดหนี้"
        verbose_name_plural = "รายการลดหนี้"

    def save(self, *args, **kwargs):
        # ราคาตามใบสั่งขาย (ต่อหน่วยบาร์โค้ด) ณ ตอนลดหนี้
        self.unit_price = self.sales_item.sale_price or Decimal('0')
        self.amount = (self.unit_price * self.quantity).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)
        self.sync_delivery_log()

    def sync_delivery_log(self):
        """สร้าง/อัปเดตแถวรับคืน (SalesDeliveryLog ติดลบ) ผ่าน .save() ปกติ — ได้ปรับสต็อก/DC/Rebate ครบ"""
        cn = self.credit_note
        si = self.sales_item
        shipped_at = timezone.make_aware(
            datetime.datetime.combine(cn.doc_date, datetime.time(10, 0)), timezone.get_current_timezone())
        log = SalesDeliveryLog.objects.filter(credit_note_item=self).first() or SalesDeliveryLog(
            credit_note_item=self, sales_order=cn.sales_order, user=cn.created_by)
        log.barcode_obj = si.barcode_obj
        log.product = si.product
        log.quantity_shipped = -self.quantity
        log.shipped_date = shipped_at
        log.notes = f"ลดหนี้ {cn.cn_number}"
        log.save()


@receiver(post_delete, sender=CreditNote)
def _refresh_payment_status_on_cn_delete(sender, instance, **kwargs):
    try:
        instance.sales_order.update_payment_status()
    except SalesOrder.DoesNotExist:
        pass


def _delivery_local_date(dt_value):
    """วันที่ (local) ของ shipped_date — ใช้เป็น key ของ 'รอบส่งของ'"""
    if hasattr(dt_value, 'date'):
        if timezone.is_aware(dt_value):
            return timezone.localtime(dt_value).date()
        return dt_value.date()
    return dt_value


def sync_receipts_for_sales_order(sales_order):
    """ทำให้ใบเสร็จของ SO นี้ตรงกับ SalesDeliveryLog ปัจจุบันเป๊ะ — 1 วันส่งของ = 1 ใบ

    รวม query ให้น้อยที่สุด: ดึง delivery log ทั้งหมดของ SO ครั้งเดียว + ใบเสร็จเดิมครั้งเดียว
    แล้ว group/คำนวณในหน่วยความจำ ไม่ยิง query ต่อรอบ
    - รอบที่ไม่มี log แล้ว -> ทำเครื่องหมายยกเลิก (เช่นแก้วันส่งของยกรอบ / ลบรายการส่งของ) ไม่ลบทิ้ง
    - วันครบกำหนด: ตั้งตอนสร้างใบใหม่ + รีเฟรชถ้ายังว่าง โดยอิง payment_due_date ที่
      SalesDeliveryLog.save() คำนวณจาก 'รอบบัญชี + เครดิตลูกค้า' ไว้แล้ว (แก้วันส่งของ ->
      log ถูก .save() ใหม่ -> เปลี่ยน key รอบ -> ได้ใบเสร็จใบใหม่พร้อมวันครบกำหนดที่คำนวณสด)
      หลังจากนั้นผู้ใช้ override เองได้ ระบบจะไม่ทับ
    """
    if not sales_order or not sales_order.pk:
        return

    logs = list(
        sales_order.delivery_logs.filter(credit_note_item__isnull=True)
        .select_related('barcode_obj', 'product')
        .order_by('shipped_date', 'id')
    )
    by_date = {}
    for log in logs:
        by_date.setdefault(_delivery_local_date(log.shipped_date), []).append(log)

    existing = {r.shipped_date: r for r in sales_order.receipts.filter(is_cancelled=False)}

    stale_ids = [r.id for dt, r in existing.items() if dt not in by_date]
    if stale_ids:
        SalesReceipt.objects.filter(id__in=stale_ids).update(is_cancelled=True, cancelled_at=timezone.now())

    vat_p = sales_order.vat_percent or Decimal('0')
    for dt, batch_logs in by_date.items():
        receipt = existing.get(dt) or SalesReceipt(sales_order=sales_order, shipped_date=dt)
        subtotal = sum((log.shipment_value for log in batch_logs), Decimal('0'))
        vat_amount = (subtotal * vat_p / Decimal('100')).quantize(Decimal('0.01'))
        grand_total = subtotal + vat_amount

        old_due = receipt.due_date
        if receipt.pk is None or receipt.due_date is None:
            receipt.due_date = next(
                (log.payment_due_date for log in reversed(batch_logs) if log.payment_due_date),
                None,
            )

        # เขียนกลับเฉพาะตอนมีอะไรเปลี่ยนจริง — กัน UPDATE ซ้ำซ้อนตอน signal ยิงถี่ๆ (bulk ship)
        if (receipt.pk is None or receipt.subtotal != subtotal
                or receipt.vat_amount != vat_amount or receipt.grand_total != grand_total
                or receipt.due_date != old_due):
            receipt.subtotal = subtotal
            receipt.vat_amount = vat_amount
            receipt.grand_total = grand_total
            receipt.save()


@receiver(post_save, sender=SalesDeliveryLog)
def _sync_receipt_on_delivery_save(sender, instance, raw=False, **kwargs):
    if raw:
        return
    sync_receipts_for_sales_order(instance.sales_order)


@receiver(post_delete, sender=SalesDeliveryLog)
def _sync_receipt_on_delivery_delete(sender, instance, **kwargs):
    try:
        so = instance.sales_order
    except SalesOrder.DoesNotExist:
        return
    if so and so.pk:
        sync_receipts_for_sales_order(so)


# 8. ระบบเอกสารสั่งผลิต
class ProductionOrder(models.Model):
    STATUS_CHOICES = [('Draft','ร่าง'),('Started','เริ่มผลิต'),('Finished','เสร็จบางส่วน'),('Completed','ปิดงาน/ครบถ้วน'),('Cancelled','ยกเลิก')]
    pd_number = models.CharField(max_length=50, unique=True, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_planned = models.PositiveIntegerField(verbose_name="จำนวนที่วางแผน")
    quantity_actual = models.PositiveIntegerField(default=0, verbose_name="ผลิตได้สะสม")
    order_date = models.DateField(default=datetime.date.today,db_index=True)
    status = models.CharField(max_length=20, default='Draft', choices=STATUS_CHOICES)
    notes = models.TextField(blank=True, verbose_name="หมายเหตุ")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    bom = models.ForeignKey('BOM', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="สูตรที่ใช้ผลิต")
    
    def clean(self):
        # Validate 1: เช็กว่า BOM ที่เลือก เป็นของสินค้าตัวนี้จริงๆ
        if self.product and self.bom:
            if self.bom.product != self.product:
                raise ValidationError({
                    'bom': f"❌ BOM '{self.bom}' ไม่ใช่สูตรของสินค้า '{self.product}' กรุณาเลือกใหม่"
                })
            
    @property
    def quantity_pending_receipt(self):
        """สำหรับหน้า C1: ยอดที่ยังผลิตไม่ครบ (รอรับ)"""
        if self.status in ['Completed', 'Cancelled']:
            return 0
        return max(0, self.quantity_planned - self.quantity_actual)
    
    def generate_material_usage(self):
        """ก๊อปปี้รายการจาก BOM มาลงตารางใช้จริง"""
        if self.bom:
            # 🛑 1. ล้างของเก่าออกก่อน (เผื่อมีการกด Save ซ้ำเพื่ออัปเดตสูตร)
            self.material_usages.all().delete()
            
            # 🛑 2. เปลี่ยนจาก .items.all() เป็น .ingredients.all() ตามโค้ดเดิมของเปรม
            for ing in self.bom.ingredients.all():
                # สูตร: (ปริมาณใน BOM แปลงเป็นหน่วยหลักแล้ว) * (จำนวนที่วางแผนผลิต)
                total_needed = ing.quantity_base * self.quantity_planned
                
                ProductionMaterialUsage.objects.create(
                    production_order=self,
                    raw_material=ing.material, # ใช้ ing.material ตามโครงสร้าง BOM ของเปรม
                    planned_qty=total_needed,
                    actual_qty_to_use=total_needed
                )

    def save(self, *args, **kwargs):
        # 1. รันเลขที่ใบ PD
        if not self.pd_number: 
            self.pd_number = generate_number('PD', ProductionOrder, 'pd_number')
        
        # 2. Auto ดึง BOM ล่าสุดมาแปะถ้ายังไม่ได้เลือก
        if not self.bom and self.product:
            # ใบสั่งผลิตไม่ผูกลูกค้า -> สูตรทุกลูกค้า (ไม่หยิบสูตรเฉพาะลูกค้ามาใช้เอง)
            self.bom = pick_bom(self.product)

        # 3. ตรรกะสถานะ (ของเปรม)
        if self.status not in ['Completed', 'Cancelled']:
            if self.quantity_actual <= 0:
                self.status = 'Draft'
            elif self.quantity_actual < self.quantity_planned:
                self.status = 'Started'
            elif self.quantity_actual >= self.quantity_planned:
                self.status = 'Finished'
        
        # ✅ บันทึกข้อมูลหลักก่อนเพื่อให้มี ID (Primary Key)
        super().save(*args, **kwargs)

        # 4. แตกรายการวัตถุดิบหลังจาก Save สำเร็จ (ต้องอยู่ภายใต้ฟังก์ชัน save)
        # เราเช็กว่ามี BOM และยังไม่มีรายการวัตถุดิบถูกสร้างมาก่อน (ป้องกันการสร้างซ้ำเวลาแก้ไขใบเดิม)
        if self.bom and not self.material_usages.exists():
            for ing in self.bom.ingredients.all():
                ProductionMaterialUsage.objects.create(
                    production_order=self,
                    raw_material=ing.material, # ใช้ .material ตามโครงสร้างสูตร
                    planned_qty=ing.quantity_base * self.quantity_planned,
                    actual_qty_to_use=ing.quantity_base * self.quantity_planned,
                    is_scrap=ing.is_scrap,
                )
    class Meta: verbose_name_plural = "O2. ใบสั่งผลิต (Productions)"


class ProductionLog(models.Model):
    production_order = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name='production_logs')
    quantity_finished = models.PositiveIntegerField(verbose_name="จำนวนที่เสร็จครั้งนี้")
    notes = models.TextField(blank=True, verbose_name="หมายเหตุ")
    finished_date = models.DateTimeField(auto_now_add=True, verbose_name="วันเวลาที่เสร็จ")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="ผู้บันทึก")

    def save(self, *args, **kwargs):
        if not self.pk:
            prod_order = self.production_order
            
            # 1. เพิ่มสต็อกสินค้าสำเร็จรูป (FG)
            prod_order.product.stock_quantity += self.quantity_finished
            prod_order.product.save()

            # 2. 🎯 ตัดสต็อกวัตถุดิบ/Package จาก "รายการที่จองไว้ในใบ PD" (ไม่ใช่จาก BOM กลาง)
            # วิธีนี้จะทำให้เปรมแก้จำนวนใช้จริงในหน้า PD ได้ และระบบจะตัดตามนั้น
            usage_ratio = Decimal(str(self.quantity_finished)) / Decimal(str(prod_order.quantity_planned))
            
            # เปลี่ยนจาก prod_order.bom.items เป็น prod_order.material_usages
            for usage in prod_order.material_usages.all():
                # คำนวณยอดตัดจาก 'จำนวนที่ระบุไว้ในใบสั่งผลิต'
                deduct_qty = usage.actual_qty_to_use * usage_ratio
                
                # หักสต็อกจริงของวัตถุดิบตัวนั้น
                usage.raw_material.stock_quantity -= deduct_qty
                usage.raw_material.save()

                # 🎯 วัตถุดิบที่ติ๊ก "เศษเสีย" ไว้ใน BOM — นอกจากตัดออกจากคลังหลักตามปกติแล้ว
                # ให้ย้าย (บวก) จำนวนที่ตัดไปนั้นเข้าคลังเศษเสียด้วย
                if usage.is_scrap:
                    scrap_wh = Warehouse.objects.filter(type='scrap').first()
                    if scrap_wh:
                        _warehouse_adjust(usage.raw_material, scrap_wh, int(deduct_qty))

                # ✅ บันทึกสะสมไว้ว่าตัดไปเท่าไหร่แล้ว เพื่อให้หน้า C1 คำนวณยอด "รอใช้" ได้แม่นยำ
                usage.used_so_far += deduct_qty
                usage.save()

            # 3. อัปเดตยอดสะสมในใบสั่งผลิต
            prod_order.quantity_actual += self.quantity_finished
            prod_order.save() 
            
        super().save(*args, **kwargs)

    # ✅ เพิ่มจุดที่ 2: ฟังก์ชันสำหรับจัดการตอน "ลบ" รายการผลิต
    def delete(self, *args, **kwargs):
        prod_order = self.production_order
        
        # 1. คืนสต็อกสินค้า (หักออก)
        prod_order.product.stock_quantity -= self.quantity_finished
        prod_order.product.save()

        # 2. คืนสต็อกวัตถุดิบ (บวกกลับเข้าสต็อก)
        bom = prod_order.bom or pick_bom(prod_order.product)
        if bom:
            for ing in bom.ingredients.all():
                return_qty = ing.quantity_base * self.quantity_finished
                ing.material.stock_quantity += return_qty
                ing.material.save()

                # 🎯 ตัวที่ตอนตัดสต็อกย้ายเข้าคลังเศษเสียไว้ด้วย ต้องคืน (หักออก) จากคลังเศษเสียด้วยเช่นกัน
                if ing.is_scrap:
                    scrap_wh = Warehouse.objects.filter(type='scrap').first()
                    if scrap_wh:
                        _warehouse_adjust(ing.material, scrap_wh, -int(return_qty))

        # 3. หักยอดผลิตสะสมคืน
        prod_order.quantity_actual -= self.quantity_finished
        prod_order.save()

        super().delete(*args, **kwargs)

class StockForecast(Product):
    class Meta:
        proxy = True
        verbose_name_plural = "F2. คาดการณ์ Stock"

class StockPlanning(Product):
    class Meta:
        proxy = True
        verbose_name_plural = "F1. ตารางการวางแผนสต็อก"

class FinanceReport(PurchaseOrder):
    class Meta:
        proxy = True
        verbose_name_plural = "A3. สรุปรายจ่าย (PO Report)"

class ShipmentPaymentReport(SalesDeliveryLog):
    class Meta:
        proxy = True
        verbose_name = "C4. สรุปรับชำระ (ตามการส่ง)"
        verbose_name_plural = "C4. สรุปรับชำระ (ตามการส่ง)"

# --- T2.1 รายการราคาสัญญาและค่าธรรมเนียม (Price List per Customer) ---
class CustomerProductContract(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="ลูกค้า")
    barcode = models.ForeignKey('ProductBarcode', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="บาร์โค้ด")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="สินค้า")
    product_tag_link = models.ForeignKey(ProductTag, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="กลุ่มสินค้า (Tag)")
    contract_price = models.DecimalField(max_digits=10, decimal_places=4, verbose_name="ราคาสัญญา")
    dc_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="ค่า DC (%)")
    rebate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Rebate (%)")

    def __str__(self):
        return f"{self.customer.company_name} - {self.product.name}"

    def clean(self):
        super().clean()
        if not self.barcode_id and not self.product_id:
            raise ValidationError({'barcode': 'กรุณาเลือกบาร์โค้ดเพื่อระบุสินค้า'})

    def save(self, *args, **kwargs):
        # product field เป็น readonly ในหน้า admin (ไม่ได้ส่งมากับฟอร์ม) ต้อง derive จาก barcode เองตรงนี้
        if self.barcode_id:
            self.product_id = self.barcode.product_id
        super().save(*args, **kwargs)

    def display_product_tags(self):
    # เช็คว่ามีสินค้า และสินค้ามีกลุ่ม (tags) หรือไม่
        if self.product and hasattr(self.product, 'tags'):
            tags = self.product.tags.all()
            if tags:
                # ดึงชื่อกลุ่มทั้งหมดมาต่อกันด้วย " , "
                return ", ".join([t.name for t in tags])
        return "-"
    
    display_product_tags.short_description = "กลุ่มสินค้า (Tag)"

    def validate_unique(self, exclude=None):
        """เตือนถ้า customer + barcode ซ้ำ ก่อนถึง DB constraint"""
        from django.core.exceptions import ValidationError
        if self.customer_id and self.barcode_id:
            qs = CustomerProductContract.objects.filter(
                customer_id=self.customer_id,
                barcode_id=self.barcode_id,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({
                    'barcode': f'ลูกค้านี้มีราคาสัญญาของบาร์โค้ดนี้อยู่แล้ว'
                })
        super().validate_unique(exclude=exclude)

    class Meta:
        verbose_name_plural = "S4. ราคาสัญญา&DC/Rebate"
        unique_together = ('customer', 'barcode')

@receiver(post_save, sender=CustomerProductContract)
@receiver(post_delete, sender=CustomerProductContract)
def recalc_product_price_on_contract_change(sender, instance, **kwargs):
    """เมื่อราคาสัญญา (CustomerProductContract) ถูกแก้ไข/ลบ ให้คำนวณ sale_price ของสินค้าที่เกี่ยวข้องใหม่"""
    instance.product.recalc_cost_and_price()

@receiver(post_save, sender=CustomerProductContract)
@receiver(post_delete, sender=CustomerProductContract)
def recalc_dc_rebate_on_contract_change(sender, instance, **kwargs):
    """เมื่อสัญญา (T2) ถูกแก้ไข/ลบ ให้คำนวณ dc_amount/rebate_amount ใหม่สำหรับใบส่งของ
    (SalesDeliveryLog/C6) ของ customer+product คู่นี้ — เฉพาะฝั่งที่ "ยังไม่ยืนยัน/ยังไม่จ่าย"
    เท่านั้น ฝั่งที่ confirm ไปแล้วถือเป็นยอดที่จ่ายจริงแล้ว ไม่แตะ

    หมายเหตุ: เดิม query หา contract ใหม่ทีละแถวใบส่งของ (N+1) แล้วยัง update ทีละแถวอีก —
    ลูกค้าที่มี T2 price contract เยอะ (เกิน ~100 รายการ) พอกด Save ฟอร์มทีเดียวจะทริกเกอร์
    signal นี้ซ้ำๆ ต่อ contract แต่ละแถว คูณกับ query ต่อแถวใบส่งของ กลายเป็น query รวมมหาศาล
    จน request ค้างเกิน timeout ของ gunicorn (WORKER TIMEOUT → error 500) — แก้โดย query หา
    contract แค่ครั้งเดียว แล้วอัปเดตใบส่งของทั้งหมดเป็นชุดเดียวด้วย bulk_update"""
    if kwargs.get('signal') is post_delete:
        contract = None
    else:
        contract = CustomerProductContract.objects.filter(
            customer_id=instance.customer_id,
            product_id=instance.product_id,
        ).first()

    logs = SalesDeliveryLog.objects.filter(
        sales_order__customer_id=instance.customer_id,
        product_id=instance.product_id,
    ).filter(
        models.Q(is_dc_confirmed=False) | models.Q(is_rebate_confirmed=False)
    )

    to_update = []
    for log in logs:
        old_dc, old_rebate = log.dc_amount, log.rebate_amount
        if contract:
            new_dc = log.shipment_value * (contract.dc_percent / 100)
            new_rebate = log.shipment_value * (contract.rebate_percent / 100)
        else:
            new_dc = Decimal('0')
            new_rebate = Decimal('0')
        if log.is_dc_confirmed:
            new_dc = old_dc
        if log.is_rebate_confirmed:
            new_rebate = old_rebate
        if new_dc != old_dc or new_rebate != old_rebate:
            log.dc_amount = new_dc
            log.rebate_amount = new_rebate
            to_update.append(log)

    if to_update:
        SalesDeliveryLog.objects.bulk_update(to_update, ['dc_amount', 'rebate_amount'])

# --- T2.2 ระบบปรับปรุงสต็อก (Stock Adjustment) ---
class StockAdjustment(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="สินค้า")
    adjustment_type = models.CharField(
        max_length=10, 
        choices=[('ADD', 'เพิ่มสต็อก (+)'), ('SUB', 'ลดสต็อก (-)')], 
        default='ADD'
    )
    quantity = models.IntegerField(verbose_name="จำนวนที่ปรับ")
    reason = models.CharField(max_length=255, verbose_name="หมายเหตุ/เหตุผล")
    adjustment_value = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # คำนวณมูลค่าตามราคาทุน (buy_price)
        self.adjustment_value = self.quantity * self.product.buy_price
        
        # ปรับปรุงยอดใน Product ทันที
        if self.adjustment_type == 'ADD':
            self.product.stock_quantity += self.quantity
        else:
            self.product.stock_quantity -= self.quantity
        
        self.product.save()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "W7. บันทึกการปรับสต็อก"

class SalesReport(Product): # ใช้ Product เป็นฐาน
    class Meta:
        proxy = True
        verbose_name = "F4. รายงานยอดขายตามสินค้า"
        verbose_name_plural = "F4. รายงานยอดขายตามสินค้า"

# --- 5. Proxy Model สำหรับหน้า C6 (Shipment Accounting) ---
# --- ในไฟล์ models.py ---
# --- ในไฟล์ models.py ---
from decimal import Decimal # 👈 อย่าลืม import ไว้ด้านบนสุดของไฟล์นะครับ

class ShipmentAccounting(SalesDeliveryLog):
    class Meta:
        proxy = True
        verbose_name = "A5. การทำบัญชี DC/Rebate"
        verbose_name_plural = "A5. การทำบัญชี DC/Rebate"

    # ✅ เปลี่ยนชื่อเป็น calculate_revenue_total ตามที่ Admin เรียกหา
    def calculate_revenue_total(self):
        """
        คำนวณยอดรับเงินเต็ม (รวม VAT) โดยไม่หัก DC/Rebate
        ลำดับ VAT: SO -> Customer -> 0%
        """
        so = self.sales_order
        if not so:
            return Decimal('0')

        # ดึงค่า VAT
        vat_p = so.vat_percent if so.vat_percent is not None else (so.customer.vat if so.customer else Decimal('0'))
        
        # ยอดสินค้าก่อนภาษี (ใช้ค่าจาก shipment_value ที่เปรมบอกว่ามีอยู่แล้ว)
        base_revenue = self.shipment_value or Decimal('0')
        
        # คำนวณยอดรวมภาษี
        total = base_revenue * (Decimal('1') + (Decimal(str(vat_p)) / Decimal('100')))
        return total

    # 💡 ถ้าเปรมอยากเก็บชื่อเดิมไว้ใช้ที่อื่นด้วย ก็ทำ Alias ไว้แบบนี้ครับ
    def calculate_gross_revenue(self):
        return self.calculate_revenue_total()

class ProductionMaterialUsage(models.Model):
    """รายการวัตถุดิบที่ "จอง" ไว้สำหรับใบสั่งผลิตนี้"""
    production_order = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name='material_usages')
    raw_material = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="วัตถุดิบ/Package")
    planned_qty = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name="จำนวนตามสูตร (Total)")
    actual_qty_to_use = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="จำนวนที่ต้องใช้จริง (ปรับแต่งได้)")
    used_so_far = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name="ตัดสต็อกไปแล้ว")
    auto_produce = models.BooleanField(default=False, verbose_name="ผลิตทันที (Auto PD)")
    is_produced = models.BooleanField(default=False, editable=False)
    is_scrap = models.BooleanField(
        default=False,
        editable=False,
        verbose_name="เศษเสีย",
        help_text="คัดลอกมาจาก BOMIngredient.is_scrap ตอนสร้างใบสั่งผลิต",
    )

    @property
    def pending_use(self):
        """สำหรับหน้า C1: ยอดรอใช้ (ที่ยังไม่ถูกตัดสต็อก)"""
        if self.production_order.status in ['Completed', 'Cancelled']:
            return 0
        return max(0, self.actual_qty_to_use - self.used_so_far)
    def load_materials_from_bom(self):
        if not self.bom:
            return

        from .models import ProductionMaterialUsage
        
        # 1. ดึงรายการจาก BOM มาสร้างรายการจองวัตถุดิบ
        for item in self.bom.items.all():
            # สูตร: (จำนวนต่อหน่วย) * (จำนวนที่แผนจะผลิต)
            total_needed = item.quantity * self.quantity_planned
            
            ProductionMaterialUsage.objects.create(
                production_order=self,
                raw_material=item.raw_material,
                planned_qty=total_needed,      # จำนวนตามสูตร
                actual_qty_to_use=total_needed, # ยอดที่ต้องใช้จริง (เริ่มต้นให้เท่ากัน)
                used_so_far=0                  # เริ่มต้นยังไม่ตัดสต็อก
            )

class AdvanceOrderRule(models.Model):
    """กฎการสั่งซื้อ/สั่งผลิตล่วงหน้าแบบซ้ำ (ทุก N วัน จนถึงวันสิ้นสุด)"""
    ORDER_TYPE_CHOICES = [('PURCHASE', 'ใบสั่งซื้อ'), ('PRODUCTION', 'ใบสั่งผลิต')]

    fo_number = models.CharField(max_length=50, unique=True, editable=False)
    order_type = models.CharField(max_length=10, choices=ORDER_TYPE_CHOICES, default='PURCHASE', verbose_name="ประเภท")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="สินค้า")

    # --- เฉพาะ PRODUCTION ---
    barcode_obj = models.ForeignKey('ProductBarcode', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="บาร์โค้ดที่จะผลิต")
    bom = models.ForeignKey('BOM', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="สูตรที่ใช้ผลิต")

    # --- เฉพาะ PURCHASE ---
    supplier = models.ForeignKey('Supplier', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="ผู้จำหน่าย")

    quantity = models.PositiveIntegerField(verbose_name="จำนวนต่อครั้ง")
    frequency_days = models.PositiveIntegerField(verbose_name="ความถี่ (ทุกกี่วัน)")
    end_date = models.DateField(null=True, blank=True, verbose_name="วันสิ้นสุด")
    next_run_date = models.DateField(default=datetime.date.today, verbose_name="รอบถัดไป")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.order_type == 'PURCHASE' and not self.supplier_id:
            raise ValidationError({'supplier': "❌ ใบสั่งซื้อล่วงหน้าต้องเลือกผู้จำหน่ายก่อน"})
        if self.order_type == 'PRODUCTION' and not self.bom_id:
            raise ValidationError({'bom': "❌ ใบสั่งผลิตล่วงหน้าต้องเลือกสูตรการผลิต (BOM) ก่อน"})
        if self.barcode_obj_id and self.product_id and self.barcode_obj.product_id != self.product_id:
            raise ValidationError({'barcode_obj': f"❌ บาร์โค้ด '{self.barcode_obj}' ไม่ใช่ของสินค้า '{self.product}' กรุณาเลือกใหม่"})

    def save(self, *args, **kwargs):
        if not self.fo_number:
            self.fo_number = generate_number('FO', AdvanceOrderRule, 'fo_number')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.fo_number} - {self.get_order_type_display()} - {self.product} (ทุก {self.frequency_days} วัน)"

    class Meta:
        verbose_name_plural = "F3. ใบสั่งผลิต/ใบสั่งซื้อล่วงหน้า"


def run_due_advance_orders():
    """สร้างใบสั่งซื้อ/ใบสั่งผลิตจริงจากกฎที่ถึงรอบแล้ว — เรียกจาก AdvanceOrderRunnerMiddleware"""
    today = datetime.date.today()
    due_rules = AdvanceOrderRule.objects.filter(next_run_date__lte=today).exclude(
        end_date__isnull=False, end_date__lt=today
    )
    for rule in due_rules:
        new_next_run = today + datetime.timedelta(days=rule.frequency_days)
        # compare-and-swap: ชนะ race แล้วค่อยสร้างเอกสารจริง กัน request คู่ขนานสร้างซ้ำ
        won = AdvanceOrderRule.objects.filter(pk=rule.pk, next_run_date=rule.next_run_date).update(next_run_date=new_next_run)
        if not won:
            continue

        if rule.order_type == 'PURCHASE':
            po = PurchaseOrder.objects.create(supplier=rule.supplier)
            PurchaseItem.objects.create(purchase_order=po, product=rule.product, quantity_unit=rule.quantity, unit_price=0)
        else:
            ProductionOrder.objects.create(product=rule.product, bom=rule.bom, quantity_planned=rule.quantity)

class InternationalPurchaseTracking(PurchaseOrder):
    class Meta:
        proxy = True
        verbose_name = "P4. ติดตามสินค้าต่างประเทศ"
        verbose_name_plural = "P4. ติดตามสินค้าต่างประเทศ"

class SalesContract(models.Model):
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, verbose_name="ลูกค้า")
    contract_name = models.CharField(max_length=255, verbose_name="ชื่อสัญญา/เลขที่สัญญา")
    start_date = models.DateField(verbose_name="วันที่เริ่มสัญญา")
    end_date = models.DateField(verbose_name="วันที่สิ้นสุดสัญญา")
    is_active = models.BooleanField(default=True, verbose_name="สถานะใช้งาน")

    PAYOUT_TRIGGER = [
        ('END_OF_CONTRACT', 'จ่ายครั้งเดียวเมื่อครบสัญญา'),
        ('ANNIVERSARY', 'จ่ายทุกวันครบรอบที่ระบุ (เช่น ทุกวันที่ 5 ของปี)'),
        ('PERIODIC', 'จ่ายตามรอบเงื่อนไข (เดือน/ไตรมาส/ปี)'),
    ]
    
    PAYOUT_DELAY = [
        ('SAME_PERIOD', 'จ่ายภายในเดือน/รอบที่เกิดยอดเลย'),
        ('NEXT_PERIOD', 'จ่ายในเดือน/รอบถัดไป'),
        ('SPECIFIC_DAY', 'จ่ายในวันที่ระบุของรอบถัดไป'),
    ]

    payout_trigger = models.CharField(max_length=30, choices=PAYOUT_TRIGGER, default='PERIODIC', verbose_name="เงื่อนไขการตัดจ่าย")
    payout_delay = models.CharField(max_length=30, choices=PAYOUT_DELAY, default='NEXT_PERIOD', verbose_name="จังหวะการโอนเงิน")
    payout_day = models.PositiveSmallIntegerField(default=5, verbose_name="จ่ายวันที่ (ระบุตัวเลข 1-31)")
    
    next_payout_date = models.DateField(null=True, blank=True, verbose_name="วันนัดจ่ายรอบถัดไป (ระบบคำนวณให้)")

    def save(self, *args, **kwargs):
        # 🤖 คำนวณวันนัดจ่ายรอบถัดไปอัตโนมัติ
        if not self.next_payout_date:
            today = timezone.now().date()

            if self.payout_trigger == 'END_OF_CONTRACT':
                target_date = self.end_date
            else:
                base_date = max(self.start_date, today)
                target_date = base_date.replace(day=min(self.payout_day, 28))

            if self.payout_delay == 'NEXT_PERIOD':
                next_month = target_date.month % 12 + 1
                year = target_date.year + (target_date.month // 12)
                target_date = target_date.replace(year=year, month=next_month)

            self.next_payout_date = target_date

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.contract_name} - {self.customer.company_name}"

    class Meta:
        verbose_name = "A7. สัญญาการขาย"
        verbose_name_plural = "A7. สัญญาการขาย"

class ContractCondition(models.Model):
    TYPE_CHOICES = [
        ('TOTAL_SALES', '1. คำนวณจากยอดขายรวม'),
        ('PRODUCT_BASED', '2. คำนวณตามสินค้า/กลุ่มสินค้า'),
    ]
    PERIOD_CHOICES = [
        ('MONTHLY', 'รายเดือน'),
        ('QUARTERLY', 'รายไตรมาส'),
        ('YEARLY', 'รายปี'),
        ('YTD', 'ยอดรวมถึงปัจจุบัน (YTD)'),
    ]
    CALC_METHOD = [
        ('PERCENT_SALES', '% จากยอดขาย'),
        ('AMOUNT_PER_QTY', 'บาทต่อจำนวนชิ้น (เฉพาะแบบที่ 2)'),
    ]

    contract = models.ForeignKey(SalesContract, on_delete=models.CASCADE, related_name='conditions')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="ประเภทเงื่อนไข")
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES, verbose_name="รอบการคำนวณ")
    
    # เจาะจงสินค้า (ใช้สำหรับแบบที่ 2)
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="สินค้าเฉพาะเจาะจง")
    product_tag_link = models.ForeignKey(ProductTag, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="กลุ่มสินค้า (Tag)")
    
    # วิธีคำนวณและค่าที่ได้
    method = models.CharField(max_length=20, choices=CALC_METHOD, verbose_name="วิธีคำนวณ")
    value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ค่าที่ระบุ (% หรือ บาท)")

    class Meta:
        verbose_name = "เงื่อนไขสัญญา"
        verbose_name_plural = "เงื่อนไขสัญญา"

class RebatePayout(models.Model):
    contract = models.ForeignKey(SalesContract, on_delete=models.CASCADE)
    period_start = models.DateField(verbose_name="ยอดสะสมตั้งแต่วันที่")
    period_end = models.DateField(verbose_name="ยอดสะสมถึงวันที่")
    payout_date = models.DateField(verbose_name="กำหนดวันที่ต้องจ่าย")
    
    total_sales_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="ยอดขายสะสมในรอบ")
    rebate_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="เงินที่ต้องจ่ายคืน")
    
    status = models.CharField(max_length=20, choices=[('PENDING', 'รอจ่าย'), ('PAID', 'จ่ายแล้ว')], default='PENDING')
    ref_invoice = models.CharField(max_length=100, blank=True, verbose_name="เลขที่ใบลดหนี้/ใบจ่ายเงิน")
    paid_date = models.DateField(null=True, blank=True, verbose_name="วันที่จ่ายจริง")
    bank_account = models.ForeignKey('BankAccount', on_delete=models.PROTECT, null=True, blank=True,
                                     related_name='+', verbose_name="จ่ายจากสมุดบัญชี")

    def recalculate_totals(self):
        """คำนวณยอดรวมใหม่จาก RebatePayoutItem ที่เชื่อมอยู่"""
        from django.db.models import Sum
        totals = self.items.aggregate(
            total_sales=Sum('delivery__shipment_value'),
            total_rebate=Sum('delivery__rebate_amount'),
        )
        RebatePayout.objects.filter(pk=self.pk).update(
            total_sales_amount=totals['total_sales'] or 0,
            rebate_amount=totals['total_rebate'] or 0,
        )
        # update() ไม่ยิง signal — ถ้าจ่ายแล้ว ให้รายการเดินบัญชีได้ยอดใหม่ด้วย
        sync_rebate_payout_ledger(RebatePayout.objects.get(pk=self.pk))

    def __str__(self):
        return f"{self.contract} | {self.period_start} – {self.period_end}"

    class Meta:
        verbose_name = "สรุปสัญญา Rebate"
        verbose_name_plural = "A6. สรุปสัญญา Rebate"


class RebatePayoutItem(models.Model):
    """รายการส่งสินค้าที่นับในรอบการคำนวณ Rebate นี้"""
    payout = models.ForeignKey(
        RebatePayout, on_delete=models.CASCADE,
        related_name='items', verbose_name="ใบสรุป Rebate"
    )
    delivery = models.ForeignKey(
        SalesDeliveryLog, on_delete=models.PROTECT,
        related_name='payout_items', verbose_name="รายการส่งของ"
    )
    shipped_date = models.DateTimeField(verbose_name="วันที่ส่งของ")

    def save(self, *args, **kwargs):
        # ซิงค์วันที่กลับไปที่ SalesDeliveryLog จริง
        SalesDeliveryLog.objects.filter(pk=self.delivery_id).update(shipped_date=self.shipped_date)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.delivery.product} | {self.shipped_date:%d/%m/%Y}"

    class Meta:
        ordering = ['shipped_date']
        verbose_name = "รายการส่งของในรอบ Rebate"


@receiver(post_save, sender=RebatePayoutItem)
@receiver(post_delete, sender=RebatePayoutItem)
def recalc_payout_on_item_change(sender, instance, **kwargs):
    """เมื่อ item เปลี่ยน (เพิ่ม/แก้/ลบ) ให้คำนวณยอดรวมใน RebatePayout ใหม่"""
    try:
        instance.payout.recalculate_totals()
    except RebatePayout.DoesNotExist:
        pass


# ============================================================
# B5. ใบเสนอราคาซื้อ (Purchase Quotation)
# ============================================================
class PurchaseQuotation(models.Model):
    pq_number = models.CharField(max_length=50, unique=True, editable=False)
    supplier = models.ForeignKey('Supplier', on_delete=models.CASCADE, verbose_name="ผู้จำหน่าย")
    quote_date = models.DateField(default=datetime.date.today, db_index=True, verbose_name="วันที่ใบเสนอราคา")
    notes = models.TextField(blank=True, verbose_name="หมายเหตุ")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def save(self, *args, **kwargs):
        if not self.pq_number:
            self.pq_number = generate_number('PQ', PurchaseQuotation, 'pq_number')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.pq_number

    class Meta:
        verbose_name = "ใบเสนอราคาซื้อ"
        verbose_name_plural = "P3. ใบเสนอราคาซื้อ (Purchase Quotation)"


class PurchaseQuotationItem(models.Model):
    quotation = models.ForeignKey(PurchaseQuotation, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="สินค้า")
    new_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ราคาซื้อใหม่")

    def __str__(self):
        return f"{self.product.name} @ {self.new_price}"

    class Meta:
        unique_together = ('quotation', 'product')


# ============================================================
# B6. ใบเสนอราคาขาย (Sales Quotation)
# ============================================================
class SalesQuotation(models.Model):
    sq_number = models.CharField(max_length=50, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="ลูกค้า")
    quote_date = models.DateField(default=datetime.date.today, db_index=True, verbose_name="วันที่ใบเสนอราคา")
    notes = models.TextField(blank=True, verbose_name="หมายเหตุ")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def save(self, *args, **kwargs):
        if not self.sq_number:
            self.sq_number = generate_number('SQ', SalesQuotation, 'sq_number')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.sq_number

    class Meta:
        verbose_name = "ใบเสนอราคาขาย"
        verbose_name_plural = "S3. ใบเสนอราคาขาย (Sales Quotation)"


class SalesQuotationItem(models.Model):
    quotation = models.ForeignKey(SalesQuotation, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="สินค้า")
    barcode = models.ForeignKey('ProductBarcode', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="บาร์โค้ด (ถ้าระบุ)")
    new_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ราคาขายใหม่")

    def __str__(self):
        return f"{self.product.name} @ {self.new_price}"

    class Meta:
        unique_together = ('quotation', 'product')
        pass


# ============================================================
# การเงิน (M): สมุดบัญชี + รายการเดินบัญชี
# ============================================================
# รายการเดินบัญชี (BankTransaction) ส่วนใหญ่ "สร้างเอง" ผ่าน signal จากเอกสารต้นทาง:
#   - รับเงินขาย / หัก DC-Rebate (SalesPayment — หน้า A4, A5)
#   - จ่ายเงินซื้อ (PurchasePaymentLog — หน้า A3)
#   - จ่าย Rebate ตามสัญญา (RebatePayout สถานะ "จ่ายแล้ว" — หน้า A6)
#   - รับเงินกู้ / ผ่อนชำระเงินกู้ตามตารางผ่อนที่ถึงกำหนด (Loan / LoanInstallment — หน้า M3)
# แก้/ลบที่ต้นทาง -> แถวในสมุดตามเอง (OneToOne CASCADE) ส่วนรายการอื่น (ค่าธรรมเนียม, โอนระหว่างบัญชี ฯลฯ) บันทึกเองได้
# amount เก็บแบบมีเครื่องหมาย: + เงินเข้า, - เงินออก
class BankAccount(models.Model):
    ACCOUNT_TYPES = [
        ('SAVINGS', 'ออมทรัพย์'),
        ('CURRENT', 'กระแสรายวัน (เช็ค)'),
        ('CREDIT', 'เครดิต'),
        ('CASH', 'เงินสด'),
        ('FACTORING', 'แฟคตอริ่ง'),
    ]
    name = models.CharField(max_length=100, verbose_name="ชื่อบัญชี")
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='SAVINGS', verbose_name="ประเภทบัญชี")
    bank_name = models.CharField(max_length=100, blank=True, verbose_name="ธนาคาร/สถาบัน")
    branch = models.CharField(max_length=100, blank=True, verbose_name="สาขา")
    account_number = models.CharField(max_length=50, blank=True, verbose_name="เลขที่บัญชี")
    opening_balance = models.DecimalField(max_digits=18, decimal_places=4, default=0,
                                          verbose_name="ยอดยกมา",
                                          help_text="ยอดเงินในบัญชี ณ วันที่ยอดยกมา (บัญชีเครดิตที่ใช้ไปแล้วใส่ติดลบ)")
    # รายการก่อนวันนี้ยังแสดงในรายการเดินบัญชี แต่ไม่นับรวมยอดคงเหลือ (ยอดยกมาครอบคลุมแล้ว)
    opening_date = models.DateField(default=datetime.date.today, verbose_name="วันที่ยอดยกมา",
                                    help_text="รายการก่อนวันนี้ไม่นับรวมในยอดคงเหลือ (รวมอยู่ในยอดยกมาแล้ว)")
    is_default = models.BooleanField(default=False, verbose_name="บัญชีหลัก",
                                     help_text="รายการรับ/จ่ายที่ไม่ได้เลือกบัญชี (เช่น ยืนยันยอดจาก A5) จะเข้าบัญชีนี้")
    is_active = models.BooleanField(default=True, verbose_name="ใช้งาน")
    notes = models.TextField(blank=True, verbose_name="หมายเหตุ")

    # ── เฉพาะบัญชีเครดิต ──
    credit_limit = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True,
                                       validators=[MinValueValidator(0)], verbose_name="วงเงินเครดิต")
    due_day = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="วันครบกำหนดชำระ (ทุกวันที่)",
                                               help_text="1-31 (เดือนที่ไม่มีวันนั้นใช้วันสิ้นเดือน)")
    overdue_interest_rate = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True,
                                                validators=[MinValueValidator(0)],
                                                verbose_name="ดอกเบี้ยเมื่อเกินกำหนด (% ต่อปี)")

    # ── เฉพาะบัญชีแฟคตอริ่ง ──
    linked_account = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='+',
                                       verbose_name="บัญชีที่ผูกรับเงินโอน")
    factoring_interest_rate = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True,
                                                  validators=[MinValueValidator(0)],
                                                  verbose_name="ดอกเบี้ยแฟคตอริ่ง (% ต่อปี)",
                                                  help_text="คิดจากยอดเบิก ตั้งแต่วันรับเงินเบิกถึงวันที่ลูกค้าจ่าย")
    advance_percent = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True,
                                          validators=[MinValueValidator(0), MaxValueValidator(100)],
                                          verbose_name="% เบิกล่วงหน้า", help_text="เช่น 75 = จ่ายเข้าบัญชีที่ผูก 75%")
    advance_days = models.PositiveSmallIntegerField(default=1, verbose_name="วันที่จ่ายเงินเบิก (+วัน)",
                                                    help_text="นับจากวันที่กด action ขายแฟคตอริ่ง: "
                                                              "+1 = วันถัดไป, +2 = วันมะรืน")
    settle_business_days = models.PositiveSmallIntegerField(
        default=2, verbose_name="รับส่วนที่เหลือหลังลูกค้าจ่าย (วันทำการ)",
        help_text="นับข้ามเสาร์-อาทิตย์ เช่น 2: ลูกค้าจ่ายวันศุกร์ -> ได้รับวันอังคาร")

    class Meta:
        verbose_name = "สมุดบัญชี"
        verbose_name_plural = "M1. สมุดบัญชี"
        ordering = ('-is_default', 'name')

    def __str__(self):
        label = f"{self.name} ({self.get_account_type_display()})"
        return f"{label} {self.account_number}" if self.account_number else label

    def clean(self):
        errors = {}
        if self.account_type == 'CREDIT':
            if self.credit_limit is None:
                errors['credit_limit'] = "บัญชีเครดิตต้องระบุวงเงิน"
            if not self.due_day:
                errors['due_day'] = "บัญชีเครดิตต้องระบุวันครบกำหนด"
        if self.due_day is not None and not 1 <= self.due_day <= 31:
            errors['due_day'] = "ระบุวันที่ 1-31"
        if self.account_type == 'FACTORING':
            if not self.linked_account_id:
                errors['linked_account'] = "บัญชีแฟคตอริ่งต้องผูกบัญชีรับเงินโอน"
            elif self.linked_account_id == self.pk or self.linked_account.account_type == 'FACTORING':
                errors['linked_account'] = "ต้องเป็นบัญชีอื่นที่ไม่ใช่บัญชีแฟคตอริ่ง"
            if self.advance_percent is None:
                errors['advance_percent'] = "ระบุ % เบิกล่วงหน้า"
            if self.factoring_interest_rate is None:
                errors['factoring_interest_rate'] = "ระบุ % ดอกเบี้ย (0 ได้)"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            BankAccount.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)

    def next_due_date(self, today=None):
        """บัญชีเครดิต: วันครบกำหนดชำระรอบถัดไป (วันนี้หรือหลังจากนี้)"""
        if not self.due_day:
            return None
        today = today or datetime.date.today()
        this_month = add_months(today.replace(day=1), 0, self.due_day)
        return this_month if this_month >= today else add_months(today.replace(day=1), 1, self.due_day)

    @property
    def current_balance(self):
        moved = self.transactions.filter(txn_date__gte=self.opening_date).aggregate(t=Sum('amount'))['t']
        return self.opening_balance + (moved or 0)


def default_bank_account_id():
    return BankAccount.objects.filter(is_default=True, is_active=True).values_list('id', flat=True).first()


class BankTransactionCategory(models.Model):
    """หมวดของรายการที่บันทึกเอง (ค่าแรง, เงินเดือน, ค่าเช่า ...) — เพิ่มเองได้"""
    name = models.CharField(max_length=100, unique=True, verbose_name="ชื่อหมวด")

    class Meta:
        verbose_name = "หมวดรายการเดินบัญชี"
        verbose_name_plural = "หมวดรายการเดินบัญชี"
        ordering = ('name',)

    def __str__(self):
        return self.name


class BankTransaction(models.Model):
    SOURCE_CHOICES = [
        ('MANUAL', 'บันทึกเอง'),
        ('SALES_PAYMENT', 'รับเงินขาย (A4/A5)'),
        ('DC_REBATE', 'หัก DC/Rebate (A5)'),
        ('PURCHASE_PAYMENT', 'จ่ายเงินซื้อ (A3)'),
        ('REBATE_PAYOUT', 'จ่าย Rebate ตามสัญญา (A6)'),
        ('LOAN_DISBURSE', 'รับเงินกู้ (M3)'),
        ('LOAN_PAYMENT', 'ผ่อนชำระเงินกู้ (M3)'),
        ('FACTORING', 'แฟคตอริ่ง: ดอกเบี้ย/โอนเข้าบัญชีที่ผูก'),
        ('TRANSFER', 'โอนระหว่างบัญชี (อีกฝั่ง)'),
    ]
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name='transactions', verbose_name="สมุดบัญชี")
    txn_date = models.DateField(default=datetime.date.today, db_index=True, verbose_name="วันที่")
    amount = models.DecimalField(max_digits=18, decimal_places=4, verbose_name="จำนวนเงิน (+เข้า / -ออก)")
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='MANUAL', editable=False,
                                   db_index=True, verbose_name="ที่มา")
    reference = models.CharField(max_length=100, blank=True, verbose_name="เอกสารอ้างอิง")
    party = models.CharField(max_length=255, blank=True, verbose_name="บริษัท/บุคคล")
    category = models.ForeignKey(BankTransactionCategory, on_delete=models.PROTECT, null=True, blank=True,
                                 verbose_name="หมวด")
    description = models.CharField(max_length=255, blank=True, verbose_name="รายละเอียด")
    sales_payment = models.OneToOneField(SalesPayment, null=True, blank=True, on_delete=models.CASCADE,
                                         related_name='bank_txn', editable=False)
    purchase_payment = models.OneToOneField(PurchasePaymentLog, null=True, blank=True, on_delete=models.CASCADE,
                                            related_name='bank_txn', editable=False)
    rebate_payout = models.OneToOneField(RebatePayout, null=True, blank=True, on_delete=models.CASCADE,
                                         related_name='bank_txn', editable=False)
    loan_drawdown = models.OneToOneField('LoanDrawdown', null=True, blank=True, on_delete=models.CASCADE,
                                         related_name='bank_txn', editable=False)
    loan_installment = models.OneToOneField('LoanInstallment', null=True, blank=True, on_delete=models.CASCADE,
                                            related_name='bank_txn', editable=False)
    # แถวที่ระบบสร้างตามแถวรับเงินแฟคตอริ่ง (ADVANCE/REMAINDER) — 1 แถวรับเงินมีได้หลายแถว (ดอกเบี้ย/โอนออก/โอนเข้า)
    factoring_payment = models.ForeignKey(SalesPayment, null=True, blank=True, on_delete=models.CASCADE,
                                          related_name='factoring_txns', editable=False)
    # โอนระหว่างบัญชี: แถวฝั่งบัญชีปลายทาง (source TRANSFER) ชี้กลับไปแถวที่ผู้ใช้บันทึก — แก้/ลบที่แถวต้นเท่านั้น
    transfer_peer = models.OneToOneField('self', null=True, blank=True, on_delete=models.CASCADE,
                                         related_name='transfer_mirror', editable=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, editable=False,
                                   verbose_name="ผู้บันทึก")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "รายการเดินบัญชี"
        verbose_name_plural = "M2. รายการเดินบัญชี"
        ordering = ('-txn_date', '-id')

    def __str__(self):
        return f"{self.txn_date:%d/%m/%Y} {self.amount:,.2f}"

    @property
    def source_obj(self):
        return (self.sales_payment or self.purchase_payment or self.rebate_payout
                or self.loan_drawdown or self.loan_installment or self.factoring_payment)

    @property
    def is_account_locked(self):
        # สมุดบัญชีของแถวเงินกู้/แฟคตอริ่ง ระบบกำหนดเอง (เงินกู้: หน้า M3, แฟคตอริ่ง: บัญชีที่ผูกใน M1)
        return bool(self.loan_drawdown_id or self.loan_installment_id or self.factoring_payment_id
                    or self.transfer_peer_id)


@receiver(post_delete, sender=BankTransaction)
def _delete_transfer_pair(sender, instance, **kwargs):
    # ลบแถวฝั่งปลายทางของการโอน -> ลบแถวต้นด้วย (ฝั่งกลับกัน CASCADE จัดการให้แล้ว) กันเหลือข้างเดียว
    if instance.transfer_peer_id:
        BankTransaction.objects.filter(pk=instance.transfer_peer_id).delete()


def _as_date(value):
    # A5 ใส่ timezone.now() (datetime) ลง DateField — ค่าใน instance ยังเป็น datetime อยู่
    return value.date() if isinstance(value, datetime.datetime) else value


@receiver(models.signals.pre_save, sender=SalesPayment)
@receiver(models.signals.pre_save, sender=PurchasePaymentLog)
def _payment_default_bank_account(sender, instance, **kwargs):
    # รายการหัก DC/Rebate ที่ลูกค้าจ่ายเดือนนั้นผ่านแฟคตอริ่ง: resync_factoring_month ย้ายไปบัญชีแฟคตอริ่งให้เอง
    if instance.pk is None and not instance.bank_account_id:
        instance.bank_account_id = default_bank_account_id()


@receiver(post_save, sender=SalesPayment)
def sync_sales_payment_ledger(sender, instance, **kwargs):
    order = instance.order
    remark = instance.remark or ''
    is_deduction = instance.amount < 0 and ('DC' in remark or 'Rebate' in remark)
    BankTransaction.objects.update_or_create(sales_payment=instance, defaults={
        'bank_account_id': instance.bank_account_id,
        'txn_date': _as_date(instance.payment_date),
        'amount': round_money(instance.amount),  # ต้นทางเก็บ 2 ตำแหน่ง (A5 ส่งยอด VAT มาเกิน) ให้ตรงกัน
        'source_type': 'DC_REBATE' if is_deduction else 'SALES_PAYMENT',
        'reference': order.so_number or '',
        'party': order.customer.company_name if order.customer_id else '',
        'description': (remark or 'รับเงินขาย')[:255],
    })


@receiver(post_save, sender=PurchasePaymentLog)
def sync_purchase_payment_ledger(sender, instance, **kwargs):
    po = instance.purchase_order
    BankTransaction.objects.update_or_create(purchase_payment=instance, defaults={
        'bank_account_id': instance.bank_account_id,
        'txn_date': _as_date(instance.payment_date),
        'amount': -round_money(instance.amount),
        'source_type': 'PURCHASE_PAYMENT',
        'reference': po.po_number or '',
        'party': po.supplier.company_name if po.supplier_id else '',
        'description': (instance.notes or 'จ่ายเงินซื้อ')[:255],
        'created_by_id': instance.user_id,
    })


@receiver(models.signals.pre_save, sender=RebatePayout)
def _rebate_payout_paid_defaults(sender, instance, **kwargs):
    if instance.status == 'PAID':
        instance.paid_date = instance.paid_date or datetime.date.today()
        if not instance.bank_account_id:
            instance.bank_account_id = default_bank_account_id()


def sync_rebate_payout_ledger(payout):
    if payout.status != 'PAID':
        BankTransaction.objects.filter(rebate_payout=payout).delete()
        return
    contract = payout.contract
    BankTransaction.objects.update_or_create(rebate_payout=payout, defaults={
        'bank_account_id': payout.bank_account_id,
        'txn_date': payout.paid_date or payout.payout_date,
        'amount': -round_money(payout.rebate_amount),
        'source_type': 'REBATE_PAYOUT',
        'reference': payout.ref_invoice or contract.contract_name,
        'party': contract.customer.company_name,
        'description': f"จ่าย Rebate {contract.contract_name} "
                       f"({payout.period_start:%d/%m/%Y}–{payout.period_end:%d/%m/%Y})"[:255],
    })


@receiver(post_save, sender=RebatePayout)
def _rebate_payout_post_save(sender, instance, **kwargs):
    sync_rebate_payout_ledger(instance)

# ── M3. เงินกู้ ──────────────────────────────────────────────────────────────
# กรอกยอดกู้ + เงื่อนไข (วันครบกำหนดงวดแรก, จำนวนงวด, วิธีผ่อน, อัตราดอกเบี้ยหลายช่วง)
# -> ระบบสร้างตารางผ่อน (LoanInstallment) ให้เอง งวดที่ถึงกำหนดจะลงรายการเดินบัญชี (เงินออก) อัตโนมัติ
# ผ่าน run_due_loan_installments() ที่ AdvanceOrderRunnerMiddleware เรียกทุกครั้งที่เปิดหน้า Admin
def add_months(date, months, day=None):
    import calendar
    m = date.month - 1 + months
    y, m = date.year + m // 12, m % 12 + 1
    return datetime.date(y, m, min(day or date.day, calendar.monthrange(y, m)[1]))


class Loan(models.Model):
    REPAYMENT_METHODS = [
        ('ANNUITY', 'ผ่อนเท่ากันทุกงวด (เงินต้น+ดอกเบี้ย)'),
        ('EQUAL_PRINCIPAL', 'เงินต้นเท่ากันทุกงวด + ดอกเบี้ยตามยอดคงเหลือ'),
        ('FIXED_PAYMENT', 'ระบุยอดผ่อนต่องวดเอง (งวดสุดท้ายจ่ายส่วนที่เหลือ)'),
    ]
    INTEREST_METHODS = [
        ('MONTHLY', 'รายเดือน (อัตราต่อปี ÷ 12)'),
        ('DAILY', 'รายวันตามจริง (อัตราต่อปี × จำนวนวัน ÷ 365)'),
    ]
    name = models.CharField(max_length=150, verbose_name="ชื่อ/เลขที่สัญญากู้")
    lender = models.CharField(max_length=255, verbose_name="ผู้ให้กู้")
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name='loans',
                                     verbose_name="สมุดบัญชี (รับเงินกู้/ตัดชำระ)")
    # รวมจาก LoanDrawdown (รับเงินต้นได้หลายครั้ง) — ระบบคำนวณเอง ดู refresh_principal()
    principal = models.DecimalField(max_digits=18, decimal_places=4, default=0, editable=False,
                                    verbose_name="เงินต้นรวม")
    loan_date = models.DateField(null=True, blank=True, editable=False, verbose_name="วันที่รับเงินต้นครั้งแรก")
    first_due_date = models.DateField(verbose_name="วันครบกำหนดงวดแรก",
                                      help_text="งวดถัดไปครบกำหนดวันเดียวกันของทุกเดือน")
    term_months = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)],
                                                   verbose_name="จำนวนงวด (เดือน)")
    repayment_method = models.CharField(max_length=20, choices=REPAYMENT_METHODS, default='ANNUITY',
                                        verbose_name="วิธีผ่อน")
    installment_amount = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True,
                                             verbose_name="ยอดผ่อนต่องวด",
                                             help_text="ใช้กับวิธี \"ระบุยอดผ่อนต่องวดเอง\"")
    interest_method = models.CharField(max_length=10, choices=INTEREST_METHODS, default='MONTHLY',
                                       verbose_name="วิธีคิดดอกเบี้ย")
    record_disbursement = models.BooleanField(default=True, verbose_name="บันทึกเงินต้นที่รับเข้าสมุดบัญชี",
                                              help_text="สร้างรายการเงินเข้าตามวันที่รับเงินต้นแต่ละครั้ง")
    is_active = models.BooleanField(default=True, verbose_name="ใช้งาน",
                                    help_text="ปิด = หยุดตัดชำระงวดที่ถึงกำหนดอัตโนมัติ")
    notes = models.TextField(blank=True, verbose_name="หมายเหตุ")

    class Meta:
        verbose_name = "เงินกู้"
        verbose_name_plural = "M3. เงินกู้"
        ordering = ('-loan_date', '-id')

    def __str__(self):
        return f"{self.name} ({self.lender})"

    def clean(self):
        # วันครบกำหนดงวดแรก vs วันที่รับเงินต้นครั้งแรก ตรวจที่ inline รับเงินต้น (LoanDrawdownFormSet)
        if self.repayment_method == 'FIXED_PAYMENT' and not self.installment_amount:
            raise ValidationError({'installment_amount': "วิธีผ่อนนี้ต้องระบุยอดผ่อนต่องวด"})

    def refresh_principal(self):
        agg = self.drawdowns.aggregate(total=Sum('amount'), first=models.Min('draw_date'))
        self.principal, self.loan_date = agg['total'] or Decimal(0), agg['first']
        Loan.objects.filter(pk=self.pk).update(principal=self.principal, loan_date=self.loan_date)

    def is_schedule_ready(self):
        return bool(self.principal and self.term_months and self.first_due_date and self.rates.exists()
                    and (self.repayment_method != 'FIXED_PAYMENT' or self.installment_amount))

    def due_dates(self):
        return [add_months(self.first_due_date, k) for k in range(self.term_months)]

    @staticmethod
    def rate_for(due_date, due_dates, rates):
        """อัตราของงวดที่ครบกำหนด due_date = แถวที่ "เริ่มมีผล" ล่าสุดก่อนหรือตรงวันนั้น"""
        best, best_start = Decimal(0), None
        for r in rates:
            if r.from_date:
                start = r.from_date
            elif r.from_period:
                start = due_dates[min(r.from_period, len(due_dates)) - 1]
            else:
                start = datetime.date.min
            if start <= due_date and (best_start is None or start >= best_start):
                best, best_start = r.annual_rate, start
        return best

    def _period_interest(self, balance, draws_in_period, prev_date, due, rate):
        """ดอกเบี้ยงวด: ยอดยกมาต้นงวดคิดตามวิธีที่เลือก + เงินต้นที่รับระหว่างงวดคิดรายวันนับจากวันที่รับ"""
        yearly = rate / 100
        if self.interest_method == 'DAILY':
            interest = balance * yearly * Decimal((due - prev_date).days) / 365
        else:
            interest = balance * rate / 1200
        for draw_date, amount in draws_in_period:
            interest += amount * yearly * Decimal((due - draw_date).days) / 365
        return round_money(interest)

    def generate_schedule(self):
        """ลบงวดที่ยังไม่ตัดบัญชี แล้วคำนวณงวดที่เหลือใหม่จากเงินต้นคงเหลือ (งวดที่ตัดบัญชีแล้วเก็บไว้ตามเดิม)
        เงินต้นรับได้หลายครั้ง: ก้อนที่รับระหว่างงวดคิดดอกเบี้ยนับจากวันที่รับ แล้วรวมเข้าเงินต้นที่ต้องผ่อนตั้งแต่งวดนั้น"""
        self.installments.filter(bank_txn__isnull=True).delete()
        posted = list(self.installments.order_by('period_no'))
        draws = list(self.drawdowns.order_by('draw_date', 'id').values_list('draw_date', 'amount'))
        if not draws:
            return
        prev_date = posted[-1].due_date if posted else draws[0][0]
        balance = (sum((a for d, a in draws if d <= prev_date), Decimal(0))
                   - sum((i.principal_amount for i in posted), Decimal(0)))
        pending = [(d, a) for d, a in draws if d > prev_date]
        start_n = posted[-1].period_no + 1 if posted else 1
        due_dates = self.due_dates()
        rates = list(self.rates.all())
        rows = []
        for n in range(start_n, self.term_months + 1):
            due = due_dates[n - 1]
            in_period = [(d, a) for d, a in pending if d <= due]
            pending = [(d, a) for d, a in pending if d > due]
            if balance <= 0 and not in_period:
                if not pending:
                    break
                prev_date = due  # ยังไม่มีเงินต้นค้าง รอรับก้อนถัดไป
                continue
            rate = self.rate_for(due, due_dates, rates)
            interest = self._period_interest(balance, in_period, prev_date, due, rate)
            balance += sum((a for d, a in in_period), Decimal(0))
            remaining = self.term_months - n + 1
            if self.repayment_method == 'EQUAL_PRINCIPAL':
                principal = balance / remaining
            elif self.repayment_method == 'FIXED_PAYMENT':
                principal = self.installment_amount - interest
            else:
                # คิดยอดผ่อนใหม่ทุกงวดจากเงินต้นคงเหลือ -> อัตราเปลี่ยนกลางสัญญา ยอดผ่อนก็ปรับตาม
                i = rate / 1200
                payment = balance / remaining if not i else balance * i / (1 - (1 + i) ** -remaining)
                principal = payment - interest
            principal = round_money(max(principal, 0))
            if n == self.term_months or principal > balance:
                principal = balance
            balance -= principal
            rows.append(LoanInstallment(loan=self, period_no=n, due_date=due, annual_rate=rate,
                                        principal_amount=principal, interest_amount=interest,
                                        total_amount=principal + interest, balance_after=balance))
            prev_date = due
        LoanInstallment.objects.bulk_create(rows)

    def recalc_balances(self):
        """หลังแก้ยอดในตารางผ่อนเอง: เงินต้นคงเหลือแต่ละงวด = เงินต้นที่รับถึงวันครบกำหนด - เงินต้นที่ผ่อนสะสม"""
        draws = list(self.drawdowns.values_list('draw_date', 'amount'))
        repaid = Decimal(0)
        for inst in self.installments.order_by('period_no', 'due_date'):
            repaid += inst.principal_amount
            balance = sum((a for d, a in draws if d <= inst.due_date), Decimal(0)) - repaid
            if inst.balance_after != balance:
                LoanInstallment.objects.filter(pk=inst.pk).update(balance_after=balance)

    @property
    def outstanding_principal(self):
        paid = self.installments.filter(bank_txn__isnull=False).aggregate(t=Sum('principal_amount'))['t']
        return self.principal - (paid or 0)


class LoanDrawdown(models.Model):
    """รับเงินต้นเงินกู้ (รับได้หลายครั้ง) — ดอกเบี้ยของแต่ละก้อนนับจากวันที่รับ"""
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='drawdowns')
    draw_date = models.DateField(default=datetime.date.today, verbose_name="วันที่รับเงินต้น")
    amount = models.DecimalField(max_digits=18, decimal_places=4, validators=[MinValueValidator(Decimal('0.01'))],
                                 verbose_name="เงินต้นที่รับ")
    notes = models.CharField(max_length=200, blank=True, verbose_name="หมายเหตุ")

    class Meta:
        verbose_name = "รับเงินต้น"
        verbose_name_plural = "รับเงินต้น (รับได้หลายครั้ง — ดอกเบี้ยนับจากวันที่รับ)"
        ordering = ('draw_date', 'id')

    def __str__(self):
        return f"{self.loan.name} {self.draw_date:%d/%m/%Y} {self.amount:,.2f}"


def sync_drawdown_ledger(drawdown):
    loan = drawdown.loan
    if not loan.record_disbursement:
        BankTransaction.objects.filter(loan_drawdown=drawdown).delete()
        return
    BankTransaction.objects.update_or_create(loan_drawdown=drawdown, defaults={
        'bank_account_id': loan.bank_account_id,
        'txn_date': drawdown.draw_date,
        'amount': drawdown.amount,
        'source_type': 'LOAN_DISBURSE',
        'reference': loan.name[:100],
        'party': loan.lender,
        'description': f"รับเงินต้นเงินกู้ {loan.name}{': ' + drawdown.notes if drawdown.notes else ''}"[:255],
    })


@receiver(post_save, sender=LoanDrawdown)
def _drawdown_sync_ledger(sender, instance, **kwargs):
    sync_drawdown_ledger(instance)


class LoanRate(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='rates')
    from_period = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="เริ่มงวดที่",
                                                   help_text="เว้นว่างทั้งสองช่อง = ตั้งแต่งวดแรก")
    from_date = models.DateField(null=True, blank=True, verbose_name="หรือ เริ่มวันที่")
    annual_rate = models.DecimalField(max_digits=8, decimal_places=4, validators=[MinValueValidator(0)],
                                      verbose_name="ดอกเบี้ย % ต่อปี")

    class Meta:
        verbose_name = "อัตราดอกเบี้ย"
        verbose_name_plural = "อัตราดอกเบี้ย (กำหนดได้หลายช่วง ตามงวดหรือวันที่)"
        ordering = ('from_period', 'from_date', 'id')

    def clean(self):
        if self.from_period and self.from_date:
            raise ValidationError("ระบุ \"เริ่มงวดที่\" หรือ \"เริ่มวันที่\" อย่างใดอย่างหนึ่ง")

    def __str__(self):
        return f"{self.annual_rate}%"


class LoanInstallment(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='installments')
    period_no = models.PositiveSmallIntegerField(verbose_name="งวดที่")
    due_date = models.DateField(db_index=True, verbose_name="วันครบกำหนด")
    annual_rate = models.DecimalField(max_digits=8, decimal_places=4, default=0, verbose_name="ดอกเบี้ย %")
    principal_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name="เงินต้น")
    interest_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name="ดอกเบี้ย")
    total_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name="ยอดชำระ")
    balance_after = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name="เงินต้นคงเหลือ")

    class Meta:
        verbose_name = "งวดผ่อนชำระ"
        verbose_name_plural = "ตารางผ่อนชำระ"
        ordering = ('period_no', 'due_date')

    def __str__(self):
        return f"{self.loan.name} งวดที่ {self.period_no}"

    def save(self, *args, **kwargs):
        self.total_amount = (self.principal_amount or 0) + (self.interest_amount or 0)
        super().save(*args, **kwargs)

    @property
    def is_posted(self):
        return hasattr(self, 'bank_txn')

    def ledger_values(self):
        loan = self.loan
        return {
            'bank_account_id': loan.bank_account_id,
            'txn_date': self.due_date,
            'amount': -self.total_amount,
            'source_type': 'LOAN_PAYMENT',
            'reference': loan.name[:100],
            'party': loan.lender,
            'description': f"ผ่อนเงินกู้ งวดที่ {self.period_no} (ต้น {self.principal_amount:,.2f} "
                           f"ดอก {self.interest_amount:,.2f})",
        }


@receiver(post_save, sender=LoanInstallment)
def _loan_installment_sync_ledger(sender, instance, created, **kwargs):
    # แก้ยอด/วันที่ของงวดที่ตัดบัญชีไปแล้ว -> รายการเดินบัญชีตาม (งวดใหม่รอ run_due_loan_installments)
    if not created:
        BankTransaction.objects.filter(loan_installment=instance).update(**instance.ledger_values())


@receiver(post_save, sender=Loan)
def _loan_sync_ledger(sender, instance, **kwargs):
    # เปลี่ยนสมุดบัญชี/ชื่อ/ติ๊กบันทึกเงินต้น -> รายการรับเงินต้นทุกครั้งตาม
    for drawdown in instance.drawdowns.all():
        sync_drawdown_ledger(drawdown)
    BankTransaction.objects.filter(loan_installment__loan=instance).update(
        bank_account_id=instance.bank_account_id, reference=instance.name[:100], party=instance.lender)


def run_due_loan_installments():
    """งวดผ่อนที่ถึงกำหนดแล้วแต่ยังไม่ตัดบัญชี -> สร้างรายการเดินบัญชี (เงินออก) — เรียกจาก middleware"""
    from django.db import IntegrityError, transaction
    today = datetime.date.today()
    due = (LoanInstallment.objects
           .filter(due_date__lte=today, bank_txn__isnull=True, loan__is_active=True)
           .select_related('loan'))
    for inst in due:
        try:
            with transaction.atomic():
                BankTransaction.objects.create(loan_installment=inst, **inst.ledger_values())
        except IntegrityError:
            pass  # request คู่ขนานตัดงวดนี้ไปแล้ว (OneToOne กันซ้ำ)


# ── แฟคตอริ่ง ──────────────────────────────────────────────────────────────
# action "ขายแฟคตอริ่ง" (S2/A4) สร้าง SalesPayment 2 แถวเข้าบัญชีแฟคตอริ่งของลูกค้า:
#   ADVANCE   = ยอดค้างรับ × % เบิกล่วงหน้า   วันที่ = วันที่กด action + advance_days
#   REMAINDER = ส่วนที่เหลือ                  วันที่ = วันที่ลูกค้าจ่ายตามปกติ (วันกำหนดรับเงิน) + settle_business_days วันทำการ
# แล้ว sync_factoring_settlement() สร้างแถวในสมุด (source FACTORING) ให้เงินวิ่งต่อไปบัญชีที่ผูก:
#   ADVANCE:   แฟคตอริ่ง -A  /  บัญชีที่ผูก +A
#   REMAINDER: ลูกค้าโอน 100% เข้าแฟคตอริ่ง -> แฟคตอริ่งหักยอดเบิก, ดอกเบี้ย (A × % × วัน ÷ 365)
#              และ DC/Rebate เต็มจำนวนที่ผู้ใช้เลือก "หักรอบเดือน" เดียวกับเดือนที่ลูกค้าจ่าย (A5, ไม่ผูกกับ SO)
#              เหลือเท่าไรโอนเข้าบัญชีที่ผูก ถ้าไม่เหลือ/ติดลบ: ไม่สร้างรายการโอน ยอดติดลบค้างในบัญชีแฟคตอริ่ง
#              ให้ผู้ใช้โอนชดเชยเองจากหน้า M2 — ทั้งหมดคำนวณใหม่ต่อ "ลูกค้า + เดือน" ที่ resync_factoring_month()
def add_business_days(date, days):
    while days > 0:
        date += datetime.timedelta(days=1)
        if date.weekday() < 5:
            days -= 1
    return date


def factoring_customer_paid_date(order):
    """วันที่ลูกค้าจ่าย = วันกำหนดรับเงินล่าสุดของการส่งของ (คิดจากวันตัดรอบบัญชี + เครดิต)"""
    due = (order.delivery_logs.filter(credit_note_item__isnull=True, payment_due_date__isnull=False)
           .order_by('-payment_due_date').values_list('payment_due_date', flat=True).first())
    if due:
        return due
    term = order.customer.payment_term if order.customer_id else 0
    return order.order_date + datetime.timedelta(days=term or 0)


def create_factoring_payments(order):
    """คืน (สร้างแล้วหรือไม่, ข้อความ)"""
    customer = order.customer
    account = customer.factoring_account if customer else None
    if not account or account.account_type != 'FACTORING' or not account.linked_account_id:
        return False, f"{order.so_number}: ลูกค้ายังไม่ได้ตั้งบัญชีแฟคตอริ่ง (หรือบัญชียังไม่ผูกบัญชีรับเงินโอน)"
    if order.payments.filter(factoring_role__gt='').exists():
        return False, f"{order.so_number}: ขายแฟคตอริ่งไปแล้ว"
    balance = round_money(order.balance_due)
    if balance <= 0:
        return False, f"{order.so_number}: ไม่มียอดค้างรับ"
    pct = account.advance_percent or Decimal(0)
    advance = round_money(balance * pct / 100)
    # เงินเบิกได้รับหลังวันที่ "กด action" (ยื่นขายแฟคตอริ่ง) ไม่ใช่วันที่ขาย
    advance_date = datetime.date.today() + datetime.timedelta(days=account.advance_days or 0)
    paid_date = max(factoring_customer_paid_date(order), advance_date)
    SalesPayment.objects.create(
        order=order, amount=advance, payment_date=advance_date, bank_account=account, factoring_role='ADVANCE',
        remark=f"แฟคตอริ่ง เบิกล่วงหน้า {pct.normalize():f}%")
    SalesPayment.objects.create(
        order=order, amount=balance - advance, bank_account=account, factoring_role='REMAINDER',
        payment_date=add_business_days(paid_date, account.settle_business_days or 0),
        factoring_customer_paid_date=paid_date, factoring_rate=account.factoring_interest_rate or 0,
        remark=f"แฟคตอริ่ง ส่วนที่เหลือ (ลูกค้าจ่าย {paid_date:%d/%m/%Y})")
    return True, ''


def _factoring_base(p):
    return {'txn_date': p.payment_date, 'source_type': 'FACTORING', 'factoring_payment': p,
            'reference': p.order.so_number or '',
            'party': p.order.customer.company_name if p.order.customer_id else ''}


def _factoring_transfer(fx, p, net, label):
    BankTransaction.objects.create(bank_account=fx, amount=-net, **_factoring_base(p),
                                   description=f"โอนเข้า {fx.linked_account.name}: {label}"[:255])
    BankTransaction.objects.create(bank_account=fx.linked_account, amount=net, **_factoring_base(p),
                                   description=f"รับโอนจากแฟคตอริ่ง {fx.name}: {label}"[:255])


def _is_factoring(account):
    return bool(account and account.account_type == 'FACTORING' and account.linked_account_id)


def sync_factoring_advance(order_id):
    """เงินเบิกล่วงหน้าของ SO: แฟคตอริ่ง -A / บัญชีที่ผูก +A"""
    BankTransaction.objects.filter(factoring_payment__order_id=order_id,
                                   factoring_payment__factoring_role='ADVANCE').delete()
    for p in SalesPayment.objects.filter(order_id=order_id, factoring_role='ADVANCE').select_related(
            'bank_account__linked_account', 'order__customer'):
        if _is_factoring(p.bank_account) and p.amount > 0:
            _factoring_transfer(p.bank_account, p, p.amount, "เบิกล่วงหน้า")


def resync_factoring_month(customer_id, month):
    """รอบเดือน `month` ของลูกค้า: ส่วนที่เหลือ (REMAINDER) ที่ลูกค้าจ่ายในเดือนนี้ หักดอกเบี้ย
    แล้วหัก DC/Rebate ที่ผู้ใช้เลือก "หักรอบเดือนนี้" (A5) เหลือเท่าไรโอนเข้าบัญชีที่ผูก
    ไม่พอหัก -> ยกยอดไปหักส่วนที่เหลือถัดไปในเดือนเดียวกัน ถ้ายังไม่พอ ติดลบค้างในบัญชีแฟคตอริ่ง (ผู้ใช้โอนชดเชยเอง)"""
    if not customer_id or not month:
        return
    month = month.replace(day=1)
    next_month = add_months(month, 1, 1)
    remainders = list(SalesPayment.objects.filter(
        order__customer_id=customer_id, factoring_role='REMAINDER',
        factoring_customer_paid_date__gte=month, factoring_customer_paid_date__lt=next_month,
    ).select_related('bank_account__linked_account', 'order__customer').order_by('factoring_customer_paid_date', 'id'))
    remainders = [r for r in remainders if _is_factoring(r.bank_account)]
    BankTransaction.objects.filter(factoring_payment__in=[r.pk for r in remainders]).delete()

    # ยอดหัก DC/Rebate ของเดือนนี้: ถ้าลูกค้าจ่ายเดือนนี้ผ่านแฟคตอริ่ง -> ลงบัญชีแฟคตอริ่ง, ไม่งั้นกลับบัญชีหลัก
    deductions = SalesPayment.objects.filter(order__customer_id=customer_id, deduct_month=month
                                             ).exclude(deduction_kind='')
    target = remainders[0].bank_account_id if remainders else None
    if target is None:
        in_fx = deductions.filter(bank_account__account_type='FACTORING')
        if in_fx.exists():
            target = default_bank_account_id()
            deductions = in_fx
        else:
            deductions = deductions.none()
    if target is not None and deductions.exists():
        ids = list(deductions.exclude(bank_account_id=target).values_list('pk', flat=True))
        SalesPayment.objects.filter(pk__in=ids).update(bank_account_id=target)
        BankTransaction.objects.filter(sales_payment_id__in=ids).update(bank_account_id=target)

    carry = -(SalesPayment.objects.filter(order__customer_id=customer_id, deduct_month=month)
              .exclude(deduction_kind='').aggregate(t=Sum('amount'))['t'] or 0)
    for r in remainders:
        fx = r.bank_account
        advance = SalesPayment.objects.filter(order_id=r.order_id, factoring_role='ADVANCE').first()
        interest, days = Decimal(0), 0
        if advance and r.factoring_rate and r.factoring_customer_paid_date:
            days = max((r.factoring_customer_paid_date - advance.payment_date).days, 0)
            interest = round_money(advance.amount * r.factoring_rate / 100 * days / 365)
        if interest:
            BankTransaction.objects.create(bank_account=fx, amount=-interest, **_factoring_base(r),
                                           description=f"ดอกเบี้ยแฟคตอริ่ง {r.factoring_rate.normalize():f}% ({days} วัน)")
        available = r.amount - interest
        used = min(carry, max(available, 0)) if carry > 0 else Decimal(0)
        carry -= used
        net = available - used
        # carry ที่เหลือหลังแถวสุดท้าย = ยอดติดลบค้างในบัญชีแฟคตอริ่งเอง (ไม่มีรายการโอน)
        if net > 0:
            label = "ส่วนที่เหลือ" + (f" (หัก DC/Rebate {used:,.2f})" if used else "")
            _factoring_transfer(fx, r, net, label)


def _month_of(value):
    return _as_date(value).replace(day=1) if value else None


def sync_factoring_settlement(order_id):
    """คำนวณแถวแฟคตอริ่งของ SO ใหม่ทั้งหมด (เงินเบิก + ทุกเดือนที่มีส่วนที่เหลือ)"""
    sync_factoring_advance(order_id)
    customer_id = SalesOrder.objects.filter(pk=order_id).values_list('customer_id', flat=True).first()
    for paid in SalesPayment.objects.filter(order_id=order_id, factoring_role='REMAINDER').values_list(
            'factoring_customer_paid_date', flat=True):
        resync_factoring_month(customer_id, _month_of(paid))


@receiver(models.signals.pre_save, sender=SalesPayment)
def _deduction_month_from_date(sender, instance, **kwargs):
    # รายการหัก DC/Rebate: เดือนที่หัก = เดือนของวันที่รายการ (แก้วันที่ใน A4 -> ย้ายเดือนตาม) จำเดือนเดิมไว้ resync
    instance._old_deduct_month = None
    if instance.pk:
        instance._old_deduct_month = (SalesPayment.objects.filter(pk=instance.pk)
                                      .values_list('deduct_month', flat=True).first())
    if instance.deduction_kind and instance.payment_date:
        instance.deduct_month = _month_of(instance.payment_date)


@receiver(post_save, sender=SalesPayment)
@receiver(post_delete, sender=SalesPayment)
def _factoring_resync(sender, instance, **kwargs):
    try:
        customer_id = instance.order.customer_id
    except SalesOrder.DoesNotExist:
        return  # ลบทั้ง SO — แถวแฟคตอริ่ง CASCADE ไปแล้ว
    if instance.factoring_role == 'ADVANCE':
        sync_factoring_settlement(instance.order_id)
    elif instance.factoring_role == 'REMAINDER':
        resync_factoring_month(customer_id, _month_of(instance.factoring_customer_paid_date))
    elif instance.deduction_kind:
        for month in {instance.deduct_month, getattr(instance, '_old_deduct_month', None)} - {None}:
            resync_factoring_month(customer_id, month)


def deduction_date_in_month(customer, month):
    """วันที่ลงรายการหัก DC/Rebate ในรอบเดือนที่เลือก = "วันกำหนดชำระเงิน" ของลูกค้าในเดือนนั้น"""
    day = customer.account_close_day if customer and customer.account_close_day else 1
    return add_months(month.replace(day=1), 0, max(1, min(day, 31)))


def apply_dc_rebate_deduction(log, kind, month):
    """ยืนยัน DC/Rebate ของรายการส่งของ -> รายการหัก (SalesPayment ติดลบ) 1 แถวต่อ log+ประเภท
    เลือกเดือนใหม่ = ย้ายแถวเดิม (ไม่สร้างซ้ำ) แล้วแฟคตอริ่งคำนวณใหม่ทั้งเดือนเก่า/ใหม่ผ่าน signal"""
    amount = log.dc_amount if kind == 'DC' else log.rebate_amount
    if not amount or amount <= 0:
        return None
    customer = log.sales_order.customer
    label = 'DC' if kind == 'DC' else 'Rebate'
    payment = (SalesPayment.objects.filter(deduction_log=log, deduction_kind=kind).order_by('id').first()
               or SalesPayment(deduction_log=log, deduction_kind=kind))
    payment.order = log.sales_order
    payment.amount = -round_money(amount)
    payment.payment_date = deduction_date_in_month(customer, month)
    payment.remark = f"หักค่า {label} สินค้า {log.product.name} [REF-ID:{log.id}] รอบ {month:%m/%Y}"[:200]
    payment.save()
    return payment
