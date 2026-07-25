from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0054_product_min_stock'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaseorder',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, editable=False, null=True, verbose_name='วันที่ยกเลิก'),
        ),
        migrations.AddField(
            model_name='salesorder',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, editable=False, null=True, verbose_name='วันที่ยกเลิก'),
        ),
    ]
