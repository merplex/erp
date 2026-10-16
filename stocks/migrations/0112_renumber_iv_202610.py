from django.db import migrations, transaction
from django.db.models import Q, Value
from django.db.models.functions import Replace

# เปลี่ยนเลข IV (ใบเสร็จ/ใบกำกับ) ตามที่ผู้ใช้ขอ 2026-10-16 — ปิดช่องเลขที่ว่างอยู่ของเดือน 10/2569
RENUMBER = [
    ('IV-202610-0043', 'IV-202610-0029'),
    ('IV-202610-0044', 'IV-202610-0033'),
    ('IV-202610-0045', 'IV-202610-0039'),
]


def renumber_receipts(apps, schema_editor):
    SalesReceipt = apps.get_model('stocks', 'SalesReceipt')
    SalesPayment = apps.get_model('stocks', 'SalesPayment')
    BankTransaction = apps.get_model('stocks', 'BankTransaction')

    olds = [old for old, _ in RENUMBER]
    news = [new for _, new in RENUMBER]
    found = set(SalesReceipt.objects.filter(receipt_number__in=olds).values_list('receipt_number', flat=True))
    if not found:
        return  # DB ใหม่ หรือเปลี่ยนไปแล้ว — ไม่ต้องทำอะไร
    taken = list(SalesReceipt.objects.filter(receipt_number__in=news).values_list('receipt_number', flat=True))
    if len(found) != len(RENUMBER) or taken:
        # ไม่ทำ error ให้ deploy ล้ม — แจ้งใน log แล้วข้ามทั้งชุด (ไม่เปลี่ยนแค่บางใบ)
        print(f"\n  ⚠️ ข้ามการเปลี่ยนเลข IV: เจอเลขเดิม {sorted(found)} (ต้องครบ 3 ใบ), "
              f"เลขใหม่ที่มีใบใช้อยู่แล้ว (รวมใบยกเลิก) {sorted(taken)}", end='')
        return

    with transaction.atomic():
        for old, new in RENUMBER:
            SalesReceipt.objects.filter(receipt_number=old).update(receipt_number=new)
            # เลข IV ที่ระบบเคยเขียนเป็นข้อความ (ขายแฟคตอริ่งราย IV): หมายเหตุแถวรับเงิน + เอกสารอ้างอิง/รายละเอียดสมุดบัญชี
            SalesPayment.objects.filter(remark__contains=old).update(
                remark=Replace('remark', Value(old), Value(new)))
            BankTransaction.objects.filter(Q(reference__contains=old) | Q(description__contains=old)).update(
                reference=Replace('reference', Value(old), Value(new)),
                description=Replace('description', Value(old), Value(new)))
            print(f"\n  เปลี่ยนเลข {old} -> {new}", end='')


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0111_cost_4_decimals'),
    ]

    operations = [
        migrations.RunPython(renumber_receipts, migrations.RunPython.noop),
    ]
