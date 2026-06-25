from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0047_backfill_purchaseorder_paid_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='auto_cost',
            field=models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=10, verbose_name='ต้นทุนอัตโนมัติ (Supplier+15%)'),
        ),
        migrations.AddField(
            model_name='product',
            name='manual_buy_price',
            field=models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=10, verbose_name='ต้นทุน (กำหนดเอง)'),
        ),
        migrations.AlterField(
            model_name='product',
            name='buy_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='ราคาทุน (ใช้จริง)'),
        ),
    ]
