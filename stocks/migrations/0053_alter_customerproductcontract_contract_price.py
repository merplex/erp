from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0052_productionmaterialusage_auto_produce'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customerproductcontract',
            name='contract_price',
            field=models.DecimalField(decimal_places=4, max_digits=10, verbose_name='ราคาสัญญา'),
        ),
    ]
