from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0050_backfill_sale_price'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productionmaterialusage',
            name='planned_qty',
            field=models.DecimalField(decimal_places=4, default=0, max_digits=12, verbose_name='จำนวนตามสูตร (Total)'),
        ),
    ]
