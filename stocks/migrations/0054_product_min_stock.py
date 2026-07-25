from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0053_alter_customerproductcontract_contract_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='min_stock',
            field=models.PositiveIntegerField(default=0, verbose_name='สต็อกขั้นต่ำ (Min Stock)'),
        ),
    ]
