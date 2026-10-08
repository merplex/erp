from django.db import migrations


def recalc_self_referencing_bom_products(apps, schema_editor):
    # สินค้าที่มีสูตร BOM ใช้ตัวเองเป็นวัตถุดิบ (เช่น ไม้แขวนอลูมิเนียม แพ็ค 3ชิ้น = ตัวเอง x12 + กล่อง,
    # ห่วงตากผ้า 2.1 = ตัวเอง x1 + ลาเบล) ต้นทุน/ราคาขายถูกคูณ/บวกเพิ่มทุกครั้งที่คำนวณใหม่จนเพี้ยน
    # -> คำนวณใหม่ครั้งเดียวด้วยตรรกะใหม่ (ข้ามสูตรที่วนกลับมาที่ตัวเอง)
    BOM = apps.get_model('stocks', 'BOM')
    if not BOM.objects.filter(product__has_bom=True).exists():
        return  # DB ใหม่/ไม่มีสูตร ไม่ต้องแตะ model จริง

    # ใช้ model จริงเพื่อเรียก recalc_cost_and_price (ตรรกะเดียวกับหน้าแอดมิน) — รันกับ DB ที่มีข้อมูล ณ migration นี้เท่านั้น
    from stocks.models import Product
    for product in Product.objects.filter(has_bom=True).prefetch_related('bom_formulas'):
        if not any(product._bom_uses_self(bom) for bom in product.bom_formulas.all()):
            continue
        before = (product.buy_price, product.sale_price)
        product.recalc_cost_and_price()
        print(f"\n  recalc {product.pk} {product.name}: ทุน {before[0]} -> {product.buy_price}, "
              f"ราคาขาย {before[1]} -> {product.sale_price}", end='')


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0107_factoring_wht_cleared'),
    ]

    operations = [
        migrations.RunPython(recalc_self_referencing_bom_products, migrations.RunPython.noop),
    ]
