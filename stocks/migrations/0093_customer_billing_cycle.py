import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0092_bom_customer'),
    ]

    operations = [
        # account_close_day ใช้เป็น "วันกำหนดชำระเงิน" มาตลอด — เปลี่ยนชื่อให้ตรงความหมาย (ค่าเดิมคงอยู่)
        migrations.RenameField(
            model_name='customer',
            old_name='account_close_day',
            new_name='payment_day',
        ),
        migrations.AlterField(
            model_name='customer',
            name='payment_day',
            field=models.IntegerField(default=25, help_text='ระบุวันที่ 1-31 (เกินวันสิ้นเดือน = สิ้นเดือน)', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(31)], verbose_name='วันกำหนดชำระเงิน'),
        ),
        migrations.AddField(
            model_name='customer',
            name='billing_cycle',
            field=models.CharField(choices=[('MONTHLY', '1 เดือน (วันที่ 1 - สิ้นเดือน)'), ('HALF_MONTH', 'ครึ่งเดือน (1-15 / 16-สิ้นเดือน)'), ('TWO_MONTHS', '2 เดือน (ม.ค.-ก.พ. / มี.ค.-เม.ย. / ...)'), ('CUSTOM', 'ระบุช่วงวันที่เอง')], default='MONTHLY', help_text='ยอดส่งของในรอบเดียวกันนับเครดิตจากวันสิ้นรอบ', max_length=20, verbose_name='รอบวางบิล'),
        ),
        migrations.AddField(
            model_name='customer',
            name='billing_ranges',
            field=models.CharField(blank=True, help_text='ใช้กับรอบ "ระบุช่วงวันที่เอง" — เช่น 1-10,11-20,21-31 (31 = วันสุดท้ายของเดือนนั้นเสมอ)', max_length=100, verbose_name='ช่วงวันที่ (ระบุเอง)'),
        ),
        migrations.AddField(
            model_name='customer',
            name='shift_weekend_to_monday',
            field=models.BooleanField(default=True, verbose_name='ครบกำหนดตรงเสาร์-อาทิตย์ เลื่อนเป็นวันจันทร์'),
        ),
        migrations.AddField(
            model_name='salespayment',
            name='receipt',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payments', to='stocks.salesreceipt', verbose_name='ใบเสร็จ/ใบกำกับ'),
        ),
    ]
