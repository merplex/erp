from collections import defaultdict
from decimal import Decimal

from django.db import migrations
from django.utils import timezone


def _receipt_number(SalesReceipt, ref_date, counters):
    # เลขที่รูปแบบเดียวกับ generate_number() (SO/PO): IV-YYYYMM-0001
    # backfill: bucket ตามเดือน "วันที่ส่งของ" ของแต่ละใบ
    base = f"IV-{ref_date.strftime('%Y%m')}-"
    if base not in counters:
        last = (SalesReceipt.objects
                .filter(receipt_number__icontains=base)
                .order_by('receipt_number')
                .values_list('receipt_number', flat=True)
                .last())
        try:
            counters[base] = int(last.split('-')[-1]) if last else 0
        except (TypeError, ValueError):
            counters[base] = 0
    counters[base] += 1
    return f"{base}{counters[base]:04d}"


def backfill(apps, schema_editor):
    SalesOrder = apps.get_model('stocks', 'SalesOrder')
    SalesDeliveryLog = apps.get_model('stocks', 'SalesDeliveryLog')
    SalesReceipt = apps.get_model('stocks', 'SalesReceipt')

    counters = {}
    so_ids = (SalesDeliveryLog.objects
              .values_list('sales_order_id', flat=True).distinct())

    for so in SalesOrder.objects.filter(id__in=list(so_ids)).iterator():
        logs = list(
            SalesDeliveryLog.objects.filter(sales_order_id=so.id)
            .order_by('shipped_date', 'id')
        )
        by_date = defaultdict(list)
        for log in logs:
            d = log.shipped_date
            if hasattr(d, 'date'):
                d = timezone.localtime(d).date() if timezone.is_aware(d) else d.date()
            by_date[d].append(log)

        vat_p = so.vat_percent or Decimal('0')
        for d, batch in sorted(by_date.items()):
            if SalesReceipt.objects.filter(sales_order_id=so.id, shipped_date=d).exists():
                continue
            subtotal = sum((l.shipment_value for l in batch), Decimal('0'))
            vat_amount = (subtotal * vat_p / Decimal('100')).quantize(Decimal('0.01'))
            due = next((l.payment_due_date for l in reversed(batch) if l.payment_due_date), None)
            SalesReceipt.objects.create(
                receipt_number=_receipt_number(SalesReceipt, d, counters),
                sales_order_id=so.id,
                shipped_date=d,
                due_date=due,
                subtotal=subtotal,
                vat_amount=vat_amount,
                grand_total=subtotal + vat_amount,
            )


def noop(apps, schema_editor):
    apps.get_model('stocks', 'SalesReceipt').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0069_salesreceipt'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
