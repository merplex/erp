import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0094_customer_payment_day_2'),
    ]

    operations = [
        # "บัญชีแฟคตอริ่ง" -> "บัญชีรับโอน" (บัญชีที่ลูกค้าโอนเข้าปกติ เลือกบัญชีประเภทใดก็ได้) — ค่าเดิมคงอยู่
        migrations.RenameField(
            model_name='customer',
            old_name='factoring_account',
            new_name='receiving_account',
        ),
        migrations.AlterField(
            model_name='customer',
            name='receiving_account',
            field=models.ForeignKey(blank=True, help_text='บัญชีที่ลูกค้าโอนเงินเข้า (รับเงินจาก A1/A2 และรายการรับเงินที่ไม่ได้เลือกบัญชีจะเข้าบัญชีนี้) — ถ้าเป็นบัญชีแฟคตอริ่ง ยอดทั้งหมดเข้าแฟคตอริ่งก่อนแล้วโอนต่อเข้าบัญชีที่ผูกไว้ และใช้กับ action "ขายแฟคตอริ่ง"', limit_choices_to={'is_active': True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='stocks.bankaccount', verbose_name='บัญชีรับโอน'),
        ),
    ]
