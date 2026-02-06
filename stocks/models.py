from decimal import Decimal
from django.db import models
from django.db.models import Sum
from django.db.models.signals import post_delete
from django.utils import timezone
from django.contrib.auth.models import User
from django.dispatch import receiver
import random # ✅ เพิ่มไว้บนสุดของไฟล์
import datetime

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
    def __str__(self): return self.name
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
    STATUS_CHOICES = [('Draft','ร่าง'),('Confirmed','ยืนยัน'),('Received','รับบางส่วน'),('Completed','ปิดงาน/ครบถ้วน'),('Cancelled','ยกเลิก')]
    po_number = models.CharField(max_length=50, unique=True, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    invoice_no_supplier = models.CharField(max_length=100, blank=True, verbose_name="เลข Invoice ผู้ขาย")
    order_date = models.DateField(default=datetime.date.today)
    status = models.CharField(max_length=20, default='Draft', choices=STATUS_CHOICES)
    notes = models.TextField(blank=True, verbose_name="หมายเหตุ")
    vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=7.00, verbose_name="VAT (%)")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    # ✅ 1. สถานะเอกสาร (เหมือนเดิม ดูแลเรื่องการสั่งของ/รับของ)
    status = models.CharField(
        max_length=20, 
        choices=[
            ('Pending', 'รอรับของ'),
            ('Received', 'รับของบางส่วน'),
            ('Completed', 'ปิดงาน/ครบถ้วน'),
            ('Cancelled', 'ยกเลิก')
        ],
        default='Pending',
        verbose_name="สถานะเอกสาร (PO Status)"
    )

    # ✅ 2. เพิ่ม: สถานะการเงิน (แยกออกมาต่างหาก)
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('Unpaid', '🔴 ยังไม่จ่าย'),
            ('Partial', '🟠 จ่ายบางส่วน'),
            ('Paid', '🟢 จ่ายครบแล้ว')
        ],
        default='Unpaid',
        verbose_name="สถานะการจ่ายเงิน"
    )
    # ✅ 3. แก้ไขฟังก์ชันคำนวณ ให้ไปอัปเดตที่ payment_status แทน
    def update_payment_status(self):
        total_paid = self.payments.aggregate(Sum('amount'))['amount__sum'] or Decimal(0)
        
        if total_paid >= self.grand_total:
            self.payment_status = 'Paid'    # จ่ายครบ
        elif total_paid > 0:
            self.payment_status = 'Partial' # จ่ายบางส่วน
        else:
            self.payment_status = 'Unpaid'  # ยังไม่จ่าย
            
        self.save(update_fields=['payment_status'])

    # --- สูตรคำนวณเงิน (ใช้แสดงผลใน Admin) ---
    @property
    def total_items_price(self):
        # ยอดรวมสินค้า (Quantity * Unit Price)
        return sum(item.total_price for item in self.items.all())
    @property
    def vat_amount(self):
        return self.total_items_price * (self.vat_percent / 100)
    @property
    def grand_total(self):
        return self.total_items_price + self.vat_amount
    @property
    def total_paid(self):
        # ยอดที่จ่ายไปแล้ว (ดึงจากตาราง PaymentLog)
        return sum(log.amount for log in self.payment_logs.all())
    @property
    def balance_due(self):
        return self.grand_total - self.total_paid
    
    def save(self, *args, **kwargs):
        if not self.po_number: self.po_number = generate_number('PO', PurchaseOrder, 'po_number')
        super().save(*args, **kwargs)
    class Meta: verbose_name_plural = "B1. ใบสั่งซื้อ (Purchase)"
    def delete(self, *args, **kwargs):
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
    order_date = models.DateField(default=datetime.date.today)
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
    
    def save(self, *args, **kwargs):
        if not self.so_number: self.so_number = generate_number('SO', SalesOrder, 'so_number')
        super().save(*args, **kwargs)
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
        # คำนวณยอดรวมจากรายการสินค้าทั้งหมด (สมมติว่าใช้ related_name='items')
        # ถ้าเปรมตั้งชื่อ related_name เป็นอย่างอื่น ให้เปลี่ยนชื่อ .items ตรงนี้ด้วยนะครับ
        total = sum(item.total_price for item in self.items.all()) if hasattr(self, 'items') else 0
        return total

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
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_ordered = models.PositiveIntegerField(verbose_name="จำนวนที่สั่งขาย")
    quantity_shipped = models.PositiveIntegerField(default=0, verbose_name="ส่งสะสม")
    # ✅ เพิ่ม 2 ฟิลด์นี้เพื่อทำ auto production ค่ะ
    auto_produce = models.BooleanField(default=False, verbose_name="ผลิตทันที (Auto PD)")
    is_produced = models.BooleanField(default=False, editable=False) # เก็บไว้หลังบ้านกันสร้างซ้ำ

    @property
    def total_price(self):
        # ✅ ดึงราคาจาก Product (sale_price) มาคูณกับ จำนวนที่สั่ง (quantity_ordered)
        price = self.product.sale_price if self.product else 0
        qty = self.quantity_ordered or 0
        return price * qty


class SalesDeliveryLog(models.Model):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='delivery_logs')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="สินค้าที่ส่ง")
    quantity_shipped = models.PositiveIntegerField(verbose_name="จำนวนที่ส่งครั้งนี้")
    shipping_no = models.CharField(max_length=100, blank=True, verbose_name="เลขใบขนส่ง/Invoice ของเรา")
    notes = models.TextField(blank=True, verbose_name="หมายเหตุ")
    shipped_date = models.DateTimeField(auto_now_add=True, verbose_name="วันเวลาที่ส่ง")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="ผู้บันทึก")

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            # 1. สมองกล: ลดสต็อกจริง
            self.product.stock_quantity -= self.quantity_shipped
            self.product.save()
            # 2. สมองกล: สะสมยอดส่งในใบ SO
            item = SalesItem.objects.get(sales_order=self.sales_order, product=self.product)
            item.quantity_shipped += self.quantity_shipped
            item.save()
            
            # 🤖 2) ออโต้สถานะ: เปลี่ยนเป็น 'ส่งบางส่วน' (Shipped)
            so = self.sales_order
            if so.status in ['Draft', 'Confirmed']:
                so.status = 'Shipped'
                so.save()
        super().save(*args, **kwargs)
        
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
    order_date = models.DateField(default=datetime.date.today)
    status = models.CharField(max_length=20, default='Draft', choices=STATUS_CHOICES)
    notes = models.TextField(blank=True, verbose_name="หมายเหตุ")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    def save(self, *args, **kwargs):
        if not self.pd_number: 
            self.pd_number = generate_number('PD', ProductionOrder, 'pd_number')
        
        # ✅ เพิ่มจุดที่ 1: ตรรกะการเปลี่ยนสถานะอัตโนมัติ
        if self.status not in ['Completed', 'Cancelled']: # ไม่แก้สถานะถ้าปิดงานหรือยกเลิกไปแล้ว
            if self.quantity_actual <= 0:
                self.status = 'Draft'
            elif self.quantity_actual < self.quantity_planned:
                self.status = 'Started'
            elif self.quantity_actual >= self.quantity_planned:
                self.status = 'Finished'
        
        super().save(*args, **kwargs)
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
            # เพิ่มสต็อกสินค้าสำเร็จรูป
            prod_order.product.stock_quantity += self.quantity_finished
            prod_order.product.save()

            # ตัดสต็อกวัตถุดิบ (BOM)
            bom = prod_order.product.bom_formulas.first()
            if bom:
                for ing in bom.ingredients.all():
                    ing.material.stock_quantity -= (ing.quantity * self.quantity_finished)
                    ing.material.save()

            # อัปเดตยอดสะสมในใบสั่งผลิต
            prod_order.quantity_actual += self.quantity_finished
            prod_order.save() # การ save ตรงนี้จะไปกระตุ้นสถานะใน ProductionOrder เองครับ
            
        super().save(*args, **kwargs)

    # ✅ เพิ่มจุดที่ 2: ฟังก์ชันสำหรับจัดการตอน "ลบ" รายการผลิต
    def delete(self, *args, **kwargs):
        prod_order = self.production_order
        
        # 1. คืนสต็อกสินค้า (หักออก)
        prod_order.product.stock_quantity -= self.quantity_finished
        prod_order.product.save()

        # 2. คืนสต็อกวัตถุดิบ (บวกกลับเข้าสต็อก)
        bom = prod_order.product.bom_formulas.first()
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
