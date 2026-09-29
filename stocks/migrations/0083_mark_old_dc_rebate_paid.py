import datetime
from zoneinfo import ZoneInfo

from django.db import migrations

# ล้างข้อมูลเก่า (ผู้ใช้สั่ง 2026-09-29): รายการส่งของก่อน 26 ก.ค. 2569 (เวลาไทย) ถือว่าจ่าย DC/Rebate แล้วทั้งหมด
# ติ๊กสถานะอย่างเดียว — ไม่สร้างรายการหักเงินใน SO / รายการเดินบัญชี (update() ไม่ยิง signal/save)
CUTOFF = datetime.datetime(2026, 7, 26, tzinfo=ZoneInfo('Asia/Bangkok'))


def mark_paid(apps, schema_editor):
    SalesDeliveryLog = apps.get_model('stocks', 'SalesDeliveryLog')
    SalesDeliveryLog.objects.filter(shipped_date__lt=CUTOFF).update(is_dc_confirmed=True, is_rebate_confirmed=True)


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0082_factoring_transfer_labels'),
    ]

    operations = [
        migrations.RunPython(mark_paid, migrations.RunPython.noop),
    ]
