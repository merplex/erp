import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0045_contract_unique_barcode'),
    ]

    operations = [
        migrations.AlterField(
            model_name='purchasepaymentlog',
            name='payment_date',
            field=models.DateField(default=datetime.date.today, verbose_name='วันที่จ่าย'),
        ),
    ]
