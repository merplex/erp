from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User # สำหรับดึงชื่อคน Login

# 1. Supplier (ต้องอยู่บนสุด เพราะ Product จะเรียกใช้)
class Supplier(models.Model):
    TYPE_CHOICES = [('Domestic', 'ในประเทศ'), ('International', 'ต่างประเทศ')]
    company_name = models.CharField(max_length=255, blank=True, verbose_name="ชื่อบริษัท")
    contact_person = models.CharField(max_length=255, verbose_name="ชื่อคนติดต่อ")
    address = models.TextField(verbose_name="ที่อยู่")
    phone = models.CharField(max_length=50, verbose_name="เบอร์โทร")
    payment_term = models.IntegerField(default=30, verbose_name="ระยะเวลาจ่ายเงิน (วัน)")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='Domestic', verbose_name="ประเภท")
    vat = models.DecimalField(max_digits=5, decimal_places=2, default=7.00, verbose_name="Vat (%)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.type == 'International':
            self.vat = 0
        super().save(*args, **kwargs)
        if not self.company_name:
            self.company_name = f"บริษัท {self.id}"
            super().save(update_fields=['company_name'])

    def __str__(self):
        return self.company_name

# 2. Customer
class Customer(models.Model):
    company_name = models.CharField(max_length=255, verbose_name="ชื่อบริษัท")
    contact_person = models.CharField(max_length=255, verbose_name="ชื่อคนติดต่อ")
    address = models.TextField(verbose_name="ที่อยู่")
    phone = models.CharField(max_length=50, verbose_name="เบอร์โทร")
    payment_term = models.IntegerField(default=30, verbose_name="ระยะเวลาจ่ายเงิน (วัน)")
    vat = models.DecimalField(max_digits=5, decimal_places=2, default=7.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name

# 3. Product (ของเดิมที่อัปเกรดเพิ่ม Field ตามเงื่อนไขใหม่)
# 1. เพิ่มตารางกลุ่มสินค้า (Product Group / Category)
class ProductCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name="ชื่อกลุ่มสินค้า")
    description = models.TextField(blank=True, verbose_name="รายละเอียด")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "กลุ่มสินค้า"


class Product(models.Model):
    name = models.CharField(max_length=255, verbose_name="ชื่อสินค้า")
    barcode = models.CharField(max_length=100, unique=True, verbose_name="บาร์โค้ด")
    # เชื่อมกับ Supplier (ทำเป็น Dropdown)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ผู้จำหน่าย")
    # กล่องสี่เหลี่ยม mark [ ] BOM
    has_bom = models.BooleanField(default=False, verbose_name="มีสูตรการผลิต (BOM)")
    category = models.ForeignKey(
        ProductCategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="กลุ่มสินค้า"
    )
    buy_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ราคาซื้อ")
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, verbose_name="ราคาขาย")
    production_lead_time = models.IntegerField(default=0, verbose_name="ระยะเวลาผลิต (วัน)")
    delivery_lead_time = models.IntegerField(default=0, verbose_name="ระยะเวลาส่งมอบ (วัน)")
    # ดึงชื่อคนสร้างจากระบบ Login
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ผู้สร้าง")
    
    # สต็อกสินค้า
    stock_quantity = models.IntegerField(default=0, verbose_name="จำนวนคงเหลือ")
    unit = models.CharField(max_length=50, default="ชิ้น", verbose_name="หน่วย")

    def save(self, *args, **kwargs):
        # Logic: ราคาขาย default เท่าราคาซื้อ
        if not self.sale_price or self.sale_price == 0:
            self.sale_price = self.buy_price
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class BOM(models.Model):
    product = models.OneToOneField('Product', on_delete=models.CASCADE, related_name='bom_formula', verbose_name="สินค้าที่จะผลิต")
    name = models.CharField(max_length=255, verbose_name="ชื่อสูตรการผลิต")
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="ราคาขาย")
    production_time = models.IntegerField(default=1, verbose_name="ระยะเวลาผลิต (วัน)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="bom_creator")
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="bom_editor")

    def __str__(self):
        return self.name

    @property
    def total_cost(self):
        # คำนวณต้นทุนรวมจากวัตถุดิบทุกรายการในสูตร
        return sum(item.subtotal for item in self.ingredients.all())

class BOMIngredient(models.Model):
    bom = models.ForeignKey(BOM, on_delete=models.CASCADE, related_name='ingredients')
    material = models.ForeignKey('Product', on_delete=models.CASCADE, verbose_name="วัตถุดิบ")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1.0, verbose_name="จำนวนที่ใช้")

    @property
    def subtotal(self):
        # ต้นทุนต่อรายการ = ราคาซื้อของวัตถุดิบ x จำนวนที่ใช้
        return self.material.buy_price * self.quantity

