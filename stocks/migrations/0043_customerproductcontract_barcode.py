from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0042_salesdeliverylog_is_barcode_locked'),
    ]

    operations = [
        migrations.AddField(
            model_name='customerproductcontract',
            name='barcode',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='stocks.productbarcode',
                verbose_name='บาร์โค้ด',
            ),
        ),
    ]
