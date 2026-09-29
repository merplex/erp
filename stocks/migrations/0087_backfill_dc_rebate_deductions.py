import re

from django.db import migrations

REF = re.compile(r"\[REF-ID:(\d+)\]")


def tag_existing_deductions(apps, schema_editor):
    """รายการหัก DC/Rebate เดิม (สร้างจาก A5, remark มี [REF-ID:x]) -> ผูกกับรายการส่งของ + รอบเดือน = เดือนของวันที่รายการ
    ถ้ามีหลายแถวของรายการส่งของ+ประเภทเดียวกัน (บั๊กเดิมบันทึกซ้ำ) ผูกแค่แถวแรก แถวที่เหลือปล่อยไว้ตามเดิม"""
    SalesPayment = apps.get_model('stocks', 'SalesPayment')
    SalesDeliveryLog = apps.get_model('stocks', 'SalesDeliveryLog')
    seen = set()
    rows = SalesPayment.objects.filter(amount__lt=0, factoring_role='', deduction_kind='',
                                       remark__contains='[REF-ID:').order_by('id')
    for p in rows:
        match = REF.search(p.remark or '')
        kind = 'DC' if 'DC' in p.remark else ('REBATE' if 'Rebate' in p.remark else None)
        if not match or not kind:
            continue
        log_id = int(match.group(1))
        if (log_id, kind) in seen or not SalesDeliveryLog.objects.filter(pk=log_id).exists():
            continue
        seen.add((log_id, kind))
        SalesPayment.objects.filter(pk=p.pk).update(
            deduction_log_id=log_id, deduction_kind=kind, deduct_month=p.payment_date.replace(day=1))


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0086_dc_rebate_deduct_month'),
    ]

    operations = [
        migrations.RunPython(tag_existing_deductions, migrations.RunPython.noop),
    ]
