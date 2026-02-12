from decimal import Decimal
from django.db import models
from django.db.models import Sum
from django.db.models.signals import post_delete
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.dispatch import receiver
import random # ✅ เพิ่มไว้บนสุดของไฟล์
import datetime

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
    class Meta: verbose_name_plural = "A1. กลุ่มสินค้า"

class ProductTag(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="ชื่อแท็ก")
    color = models.CharField(max_length=7, default=get_random_color, verbose_name="สีแท็ก (Hex)")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="วันที่สร้าง")

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "แท็กสินค้า"
        verbose_name_plural = "T1. แท็กสินค้า (Product Tag)"

# 2. ผู้จำหน่าย
class Supplier(models.Model):
    TYPE_CHOICES = [('Domestic', 'ในประเทศ'), ('International', 'ต่างประเทศ')]
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
        super().save(*args, **kwargs)
    def __str__(self): return self.company_name
    class Meta: verbose_name_plural = "A2. ผู้จำหน่าย (Supplier)"

# 3. ลูกค้า
class Customer(models.Model):
    company_name = models.CharField(max_length=255, verbose_name="ชื่อบริษัท")
    contact_person = models.CharField(max_length=255, verbose_name="ชื่อคนติดต่อ")
    address = models.TextField(verbose_name="ที่อยู่")
    phone = models.CharField(max_length=50, verbose_name="เบอร์โทร")
    payment_term = models.IntegerField(default=30, verbose_name="Credit (วัน)")
    vat = models.DecimalField(max_digits=5, decimal_places=2, default=7.00)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True) # แก้ไขจาก auto_True เป็น auto_now
    def __str__(self): return self.company_name
    account_close_day = models.IntegerField(
        default=25, 
        verbose_name="วันที่ตัดรอบบัญชี",
        help_text="ระบุวันที่ 1-31"
    )
    class Meta: verbose_name_plural = "A3. ลูกค้า (Customer)"

# 4. รายการสินค้า
class Product(models.Model):
    name = models.CharField(max_length=255, verbose_name="ชื่อสินค้า")
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True)
    # ✅ เพิ่มฟิลด์แยกประเภท (True = สินค้ามีสต็อก, False = บริการ/ค่าใช้จ่าย)
    is_product = models.BooleanField(default=True, verbose_name="เป็นสินค้า (สต็อก)")
    tags = models.ManyToManyField(ProductTag, blank=True, related_name='products', verbose_name="แท็ก")
    suppliers = models.ManyToManyField(Supplier, through='ProductSupplier', related_name='products')
    has_bom = models.BooleanField(default=False, verbose_name="สินค้าผลิตเอง (BOM)")
    buy_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ราคาทุน")
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, verbose_name="ราคาขาย")
    unit = models.CharField(max_length=50, default="ชิ้น", verbose_name="หน่วย")
    stock_quantity = models.IntegerField(default=0, verbose_name="สต็อกปัจจุบัน")
    production_lead_time = models.IntegerField(default=0, blank=True, null=True, verbose_name="ระยะเวลาผลิต (วัน)")
    delivery_lead_time = models.IntegerField(default=0, verbose_name="ระยะเวลาส่งมอบ (วัน)")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="prod_created")
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="prod_updated")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def save(self, *args, **kwargs):
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
        last_entry = self.barcodes.all().last()
        return last_entry.code if last_entry else "-"

    class Meta: verbose_name_plural = "A4. รายการสินค้า (Product)"

class ProductBarcode(models.Model):
    product = models.ForeignKey(Product, related_name='barcodes', on_delete=models.CASCADE)
    code = models.CharField(max_length=100, unique=True, verbose_name="บาร์โค้ด")
    created_at = models.DateTimeField(auto_now_add=True)
    conversion_factor = models.PositiveIntegerField(default=1, verbose_name="จำนวนต่อหน่วย")
    unit_name = models.CharField(max_length=20, blank=True, null=True, verbose_name="ชื่อหน่วย")

    @property
    def unit_display(self):
        # ถ้าตัวคูณเป็น 1 หรือไม่ได้ใส่ชื่อหน่วย ให้ถือว่าเป็นหน่วยปกติ
        if self.conversion_factor <= 1 or not self.unit_name:
            return "หน่วยปกติ (ชิ้น)"
        return f"{self.unit_name} ({self.conversion_factor} ชิ้น)"
    
    def __str__(self):
        return self.code



class ProductSupplier(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_suppliers')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, verbose_name="ผู้จำหน่าย")
    supplier_sku = models.CharField(max_length=100, blank=True, verbose_name="รหัสสินค้าฝั่ง Supplier")
    latest_buy_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ทุนล่าสุดจากเจ้านี้")
    class Meta: unique_together = ('product', 'supplier')

# 5. สูตรการผลิต (BOM)
class BOM(models.Model):
    # แก้ไขจาก OneToOneField เป็น ForeignKey และเปลี่ยน related_name เป็นพหูพจน์
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='bom_formulas')
    name = models.CharField(max_length=255, verbose_name="ชื่อสูตร")
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50, default="ชิ้น", verbose_name="หน่วยผลิต")
    production_time = models.IntegerField(default=1, verbose_name="เวลาผลิต (วัน)")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="bom_creator")
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="bom_editor")
    @property
    def total_cost(self): return sum(item.subtotal for item in self.ingredients.all())
    def __str__(self):
        # โชว์แบบนี้: "เสื้อยืด XL - สูตรมาตรฐาน (v.1)" อ่านง่ายขึ้นเยอะ
        return f"{self.product.name} - {self.name}"
    class Meta: verbose_name_plural = "A5. สูตรการผลิต (BOM)"

class BOMIngredient(models.Model):
    bom = models.ForeignKey(BOM, on_delete=models.CASCADE, related_name='ingredients')
    material = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="วัตถุดิบ")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1.0)
    @property
    def subtotal(self): return self.material.buy_price * self.quantity
    @property
    def get_unit(self): return self.material.unit if self.material else "-"

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

    class Meta:
        verbose_name_plural = "B1. ใบสั่งซื้อ (Purchase)"

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
        if hasattr(self, 'payments'):
            return self.payments.aggregate(t=Sum('amount'))['t'] or Decimal(0)
        return Decimal(0)

    @property
    def balance_due(self):
        return self.grand_total - self.total_paid_amount

    # ==========================================
    # 🚀 LOGIC: UPDATE STATUS
    # ==========================================
    def update_status(self):
        """เรียกเมื่อมีการเปลี่ยนแปลง Receipt Log"""
        total_ordered = self.items.aggregate(t=Sum('quantity'))['t'] or 0
        total_received = self.receipt_logs.aggregate(t=Sum('quantity'))['t'] or 0

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
        total = self.grand_total
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

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # ✅ ป้องกันการลบข้อมูลจริงถ้ารับของไปแล้ว
        if self.receipt_logs.exists():
            self.status = 'Cancelled'
            self.save()
        else:
            super().delete(*args, **kwargs)

class PurchaseItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_ordered = models.PositiveIntegerField(verbose_name="จำนวนที่สั่งซื้อ")
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
    payment_date = models.DateTimeField(auto_now_add=True, verbose_name="วันที่จ่าย")
    notes = models.CharField(max_length=200, blank=True, verbose_name="หมายเหตุ/เลขที่สลิป")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="ผู้บันทึก")

    def __str__(self): return f"{self.amount}"

class PurchaseReceiptLog(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='receipt_logs')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="สินค้าที่รับ")
    quantity_received = models.PositiveIntegerField(verbose_name="จำนวนที่รับครั้งนี้")
    supplier_invoice = models.CharField(max_length=100, blank=True, verbose_name="เลข Invoice/ใบส่งของ Supplier")
    notes = models.TextField(blank=True, verbose_name="หมายเหตุ")
    received_date = models.DateTimeField(auto_now_add=True, verbose_name="วันเวลาที่บันทึก")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="ผู้บันทึก")
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            self.product.stock_quantity += self.quantity_received
            self.product.save()
            item = PurchaseItem.objects.get(purchase_order=self.purchase_order, product=self.product)
            item.quantity_received += self.quantity_received
            item.save()
            po = self.purchase_order
            if po.status in ['Draft', 'Confirmed']:
                po.status = 'Received'
                po.save()
        super().save(*args, **kwargs)

# --- ย้ายออกมานอก Class และจัดแนวแถวให้ตรงกัน ---
@receiver(post_delete, sender=PurchaseReceiptLog)
def handle_receipt_deletion(sender, instance, **kwargs):
    instance.product.stock_quantity -= instance.quantity_received
    instance.product.save()
    try:
        item = PurchaseItem.objects.get(purchase_order=instance.purchase_order, product=instance.product)
        item.quantity_received -= instance.quantity_received
        item.save()
    except:
        pass
    po = instance.purchase_order
    if not po.receipt_logs.exists() and po.status == 'Received':
        po.status = 'Confirmed'
        po.save()

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

    @property
    def total_items_price(self):
        # ✅ ตอนนี้เรียก item.total_price ได้แล้ว เพราะเราสร้างไว้ข้างบน
        return sum(item.total_price for item in self.items.all())

    @property
    def grand_total(self):
        # สมมติ VAT 7% (ถ้าเปรมมีฟิลด์ vat_percent ให้เปลี่ยนเลข 7 เป็น self.vat_percent นะครับ)
        subtotal = self.total_items_price
        vat = (subtotal * self.vat_percent) / 100 
        return subtotal + vat

    @property
    def balance_due(self):
        # ยอดค้างรับ = ยอดสุทธิ - ยอดที่รับเงินมาแล้ว
        total_paid = sum(p.amount for p in self.payments.all()) if hasattr(self, 'payments') else 0
        return self.grand_total - total_paid
    
    def __str__(self):
        return self.so_number
    
    def save(self, *args, **kwargs):
        if not self.so_number: self.so_number = generate_number('SO', SalesOrder, 'so_number')
        super().save(*args, **kwargs)
    class Meta: verbose_name_plural = "B2. ใบสั่งขาย (Sales)"


    class Meta: verbose_name_plural = "B2. ใบสั่งขาย (Sales)"
    def delete(self, *args, **kwargs):
        if self.status == 'Draft':
            super().delete(*args, **kwargs) # ถ้าเป็น Draft ลบทิ้งจริงๆ ได้
        else:
            self.status = 'Cancelled' # ถ้าสถานะอื่น เปลี่ยนเป็น 'ยกเลิก' แทน
            self.save()

    # ✅ เพิ่มสถานะการเงิน
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('Unpaid', '🔴 ยังไม่รับเงิน'),
            ('Partial', '🟠 รับเงินบางส่วน'),
            ('Paid', '🟢 รับเงินครบแล้ว')
        ],
        default='Unpaid',
        verbose_name="สถานะการรับเงิน"
    )

    # ✅ แก้ฟังก์ชันคำนวณ
    def update_payment_status(self):
        total_received = self.payments.aggregate(Sum('amount'))['amount__sum'] or Decimal(0)
        
        if total_received >= self.grand_total:
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

    def __str__(self):
        return f"รับเงิน {self.amount:,.2f}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # บันทึกเสร็จ ให้ไปอัปเดตสถานะที่ใบสั่งขายทันที
        self.order.update_payment_status()

# --- 4. Proxy Model สำหรับหน้า C3 (Income Report) ---
class IncomeReport(SalesOrder):
    class Meta:
        proxy = True
        verbose_name = "C3. สรุปรายรับ (Income Report)"
        verbose_name_plural = "C3. สรุปรายรับ (Income Report)"

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
        # ยอดค้างรับ = ยอดรวมสุทธิ - ยอดที่จ่ายแล้ว
        return self.grand_total - self.total_paid

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
        verbose_name="ราคาขายต่อหน่วย"
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
            
            # เลือก BOM ตามบาร์โค้ด (ถ้าว่าง)
            if not self.bom:
                from .models import BOM
                target_bom = BOM.objects.filter(name=self.barcode_obj.code).first()
                if not target_bom:
                    target_bom = BOM.objects.filter(product=self.product).order_by('-id').first()
                self.bom = target_bom
        else:
            # กรณีไม่มีบาร์โค้ด (เลือกสินค้าเอง)
            self.quantity_ordered = self.quantity_unit
            # ดึง BOM ล่าสุดของสินค้านั้น
            if self.product and not self.bom:
                from .models import BOM
                self.bom = BOM.objects.filter(product=self.product).order_by('-id').first()

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
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="สินค้าที่ส่ง")
    quantity_shipped = models.PositiveIntegerField(verbose_name="จำนวน")
    shipping_no = models.CharField(max_length=100, blank=True, verbose_name="เลขใบขนส่ง/Invoice ของเรา")
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
    is_revenue_confirmed = models.BooleanField(default=False, verbose_name="Paid")
    is_dc_confirmed = models.BooleanField(default=False, verbose_name="DC")
    is_rebate_confirmed = models.BooleanField(default=False, verbose_name="Rebate")
    confirmed_date = models.DateTimeField(null=True, blank=True)
    # 🎯 ฟิลด์อ้างอิงการจ่ายเงิน (ถ้ามี)
    payment_note = models.CharField(max_length=255, blank=True, verbose_name="หมายเหตุการจ่าย")

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            # --- 🚀 [LOGIC เดิมของเปรม] ---
            # 1. สมองกล: ลดสต็อกจริง
            self.product.stock_quantity -= self.quantity_shipped
            self.product.save()

            # 2. สมองกล: สะสมยอดส่งในใบ SO
            item = SalesItem.objects.get(sales_order=self.sales_order, product=self.product)
            item.quantity_shipped += self.quantity_shipped
            item.save()
            
            # 🤖 ออโต้สถานะ: เปลี่ยนเป็น 'ส่งบางส่วน' (Shipped)
            so = self.sales_order
            if so.status in ['Draft', 'Confirmed']:
                so.status = 'Shipped'
                so.save()
            # --- 🛑 [จบ LOGIC เดิม] ---


            # --- 2. [ส่วนที่เรเพิ่มให้: คำนวณเงินแยกถัง] ---
            # คำนวณมูลค่าสินค้าดิบ (ราคาขาย x จำนวนส่ง)
            self.shipment_value = item.sale_price * self.quantity_shipped

            # ดึงข้อมูล DC/Rebate จากสัญญา (Price List) มาคำนวณแยกเก็บเป็น "บาท"
            from .models import CustomerProductContract 
            contract = CustomerProductContract.objects.filter(
                customer=so.customer, 
                product=self.product
            ).first()
            
            if contract:
                # แยกเก็บค่า DC และ Rebate ลงคอลัมน์ของตัวเองชัดๆ
                self.dc_amount = self.shipment_value * (contract.dc_percent / 100)
                self.rebate_amount = self.shipment_value * (contract.rebate_percent / 100)
            else:
                self.dc_amount = 0
                self.rebate_amount = 0

            # --- 3. [คำนวณวันจ่ายเงินตามรอบบัญชี] ---
            if so.customer:
                close_day = so.customer.account_close_day
                term = so.customer.payment_term
                ref_date = datetime.date.today()

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

    @property
    def total_with_vat(self):
        # ยอดรับเงินจริง = (ยอดสินค้า - ยอดหัก DC - ยอดหัก Rebate) + VAT
        net_before_vat = self.shipment_value - self.dc_amount - self.rebate_amount
        vat_p = self.sales_order.vat_percent or 0
        return net_before_vat * (1 + (vat_p / 100))
        
@receiver(post_delete, sender=SalesDeliveryLog)
def handle_delivery_deletion(sender, instance, **kwargs):
    # 1. คืนสต็อกสินค้า
    instance.product.stock_quantity += instance.quantity_shipped
    instance.product.save()
    # 2. หักยอดส่งสะสมใน SO
    try:
        item = SalesItem.objects.get(sales_order=instance.sales_order, product=instance.product)
        item.quantity_shipped -= instance.quantity_shipped
        item.save()
    except: pass
    
    # 🤖 ออโต้สถานะ: ถ้าลบจนไม่เหลือประวัติส่งเลย ให้กลับไปเป็น 'ยืนยัน'
    so = instance.sales_order
    if not so.delivery_logs.exists() and so.status == 'Shipped':
        so.status = 'Confirmed'
        so.save()


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
                # สูตร: (ปริมาณใน BOM) * (จำนวนที่วางแผนผลิต)
                total_needed = ing.quantity * self.quantity_planned
                
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
            # ใช้ related_name 'bom_formulas' ตามที่เปรมตั้งไว้ใน BOM
            self.bom = self.product.bom_formulas.order_by('-id').first()

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
                    planned_qty=ing.quantity * self.quantity_planned,
                    actual_qty_to_use=ing.quantity * self.quantity_planned
                )
    class Meta: verbose_name_plural = "B3. ใบสั่งผลิต (Productions)"


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
        bom = prod_order.bom or prod_order.product.bom_formulas.first()
        if bom:
            for ing in bom.ingredients.all():
                ing.material.stock_quantity += (ing.quantity * self.quantity_finished)
                ing.material.save()

        # 3. หักยอดผลิตสะสมคืน
        prod_order.quantity_actual -= self.quantity_finished
        prod_order.save()

        super().delete(*args, **kwargs)

class StockPlanning(Product):
    class Meta:
        proxy = True
        verbose_name_plural = "C1. ตารางการวางแผนสต็อก"

class FinanceReport(PurchaseOrder):
    class Meta:
        proxy = True
        verbose_name_plural = "C2. สรุปรายจ่าย (Purchase Report)"

class ShipmentPaymentReport(SalesDeliveryLog):
    class Meta:
        proxy = True
        verbose_name = "C4. สรุปรับชำระ (ตามการส่ง)"
        verbose_name_plural = "C4. สรุปรับชำระ (ตามการส่ง)"

# --- T2.1 รายการราคาสัญญาและค่าธรรมเนียม (Price List per Customer) ---
class CustomerProductContract(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="ลูกค้า")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="สินค้า")
    contract_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ราคาสัญญา")
    dc_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="ค่า DC (%)")
    rebate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Rebate (%)")

    def __str__(self):
        return f"{self.customer.company_name} - {self.product.name}"

    class Meta:
        verbose_name_plural = "T2. ราคาสัญญา&DC/Rebate"
        unique_together = ('customer', 'product')

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
        verbose_name_plural = "T3. บันทึกการปรับสต็อก"

class SalesReport(Product): # ใช้ Product เป็นฐาน
    class Meta:
        proxy = True
        verbose_name = "C5. รายงานยอดขายตามสินค้า"
        verbose_name_plural = "C5. รายงานยอดขายตามสินค้า"

# --- 5. Proxy Model สำหรับหน้า C6 (Shipment Accounting) ---
# --- ในไฟล์ models.py ---
# --- ในไฟล์ models.py ---
from decimal import Decimal # 👈 อย่าลืม import ไว้ด้านบนสุดของไฟล์นะครับ

class ShipmentAccounting(SalesDeliveryLog):
    class Meta:
        proxy = True
        verbose_name = "C6. การทำบัญชี DC/Rebate"
        verbose_name_plural = "C6. การทำบัญชี DC/Rebate"

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
    planned_qty = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="จำนวนตามสูตร (Total)")
    actual_qty_to_use = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="จำนวนที่ต้องใช้จริง (ปรับแต่งได้)")
    used_so_far = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="ตัดสต็อกไปแล้ว")

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
    
class InternationalPurchaseTracking(PurchaseOrder):
    class Meta:
        proxy = True
        verbose_name = "B4. ติดตามสินค้าต่างประเทศ"
        verbose_name_plural = "B4. ติดตามสินค้าต่างประเทศ"