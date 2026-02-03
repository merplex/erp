from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True)
    
    # เพิ่ม Barcode (เผื่อเอาไว้ใช้กับเครื่องสแกนในอนาคต)
    barcode = models.CharField(max_length=100, blank=True, null=True)
    
    # เพิ่มราคาต้นทุน และราคาขาย
    # max_digits=10 คือจำนวนตัวเลขทั้งหมด, decimal_places=2 คือทศนิยม 2 ตำแหน่ง
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    stock_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit = models.CharField(max_length=20, default="ชิ้น")
    
    # เพิ่มฟิลด์รูปภาพสินค้า (รูปจะถูกเก็บไว้ที่ Hostatom หรือ Railway ตามที่เราตั้งค่าไว้)
    image = models.ImageField(upload_to='product_images/', blank=True, null=True)
    
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Logic: ถ้าไม่ได้ระบุราคาขาย (sale_price) ให้ใช้ราคาต้นทุน (price) เป็นค่าเริ่มต้น
        if not self.sale_price or self.sale_price == 0:
            self.sale_price = self.price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.sku})"
