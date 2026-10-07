from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations
from django.db.models import F, Sum


def recompute(apps, schema_editor):
    # เดิม P2/P4 เลือกสถานะการเงินเองได้ ใบเก่าจึงค้างสถานะไม่ตรงกับรายการจ่ายเงิน (เช่น จ่ายบางส่วน แต่ไม่มีรายการจ่าย)
    # -> คำนวณใหม่จากรายการจ่ายเงิน A3 เทียบยอดสุทธิ (ยกเว้นปิดยอดกรณีพิเศษ)
    PurchaseOrder = apps.get_model('stocks', 'PurchaseOrder')
    for po in PurchaseOrder.objects.exclude(payment_status='SETTLED'):
        subtotal = po.items.aggregate(t=Sum(F('quantity_ordered') * F('unit_price')))['t'] or Decimal(0)
        total = (subtotal * (1 + (po.vat_percent or 0) / Decimal(100))).quantize(Decimal('0.01'), ROUND_HALF_UP)
        if total <= 0:
            continue
        paid = po.payment_logs.aggregate(t=Sum('amount'))['t'] or Decimal(0)
        status = 'Paid' if paid >= total else 'Partial' if paid > 0 else 'Unpaid'
        if status != po.payment_status:
            PurchaseOrder.objects.filter(pk=po.pk).update(payment_status=status)


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0100_salesorder_payment_status_factored'),
    ]

    operations = [
        migrations.RunPython(recompute, migrations.RunPython.noop),
    ]
