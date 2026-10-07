from django.db import migrations


def recompute(apps, schema_editor):
    # เดิมแก้รายการสินค้า/VAT ใน S2 หรือลบรายการรับเงินนอกหน้า A4 แล้วสถานะรับเงินไม่คำนวณใหม่ -> ค้างไม่ตรงยอด
    # ใช้โมเดลจริง (ตรรกะแฟคตอริ่ง/ใบลดหนี้/ยอดรายการสินค้าอยู่ในเมธอด) — ยกเว้นปิดยอดกรณีพิเศษ
    from stocks.models import SalesOrder
    for so in SalesOrder.objects.exclude(payment_status='SETTLED').iterator():
        so.update_payment_status()


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0101_recompute_po_payment_status'),
    ]

    operations = [
        migrations.RunPython(recompute, migrations.RunPython.noop),
    ]
