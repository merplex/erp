import datetime
from zoneinfo import ZoneInfo

from django.db import migrations

# ล้างข้อมูลเก่า (ผู้ใช้สั่ง 2026-09-29): รายการส่งของก่อน 26 ก.ค. 2569 (เวลาไทย) ติ๊ก Paid (ยืนยันรับเงิน) ทั้งหมด
# ติ๊กสถานะอย่างเดียว — ไม่สร้างรายการรับเงินใน SO / รายการเดินบัญชี (update() ไม่ยิง signal/save)
CUTOFF = datetime.datetime(2026, 7, 26, tzinfo=ZoneInfo('Asia/Bangkok'))


def mark_paid(apps, schema_editor):
    SalesDeliveryLog = apps.get_model('stocks', 'SalesDeliveryLog')
    SalesDeliveryLog.objects.filter(shipped_date__lt=CUTOFF).update(is_revenue_confirmed=True)


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0087_backfill_dc_rebate_deductions'),
    ]

    operations = [
        migrations.RunPython(mark_paid, migrations.RunPython.noop),
    ]
