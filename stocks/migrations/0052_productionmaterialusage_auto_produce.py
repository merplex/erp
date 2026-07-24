from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0051_alter_productionmaterialusage_planned_qty'),
    ]

    operations = [
        migrations.AddField(
            model_name='productionmaterialusage',
            name='auto_produce',
            field=models.BooleanField(default=False, verbose_name='ผลิตทันที (Auto PD)'),
        ),
        migrations.AddField(
            model_name='productionmaterialusage',
            name='is_produced',
            field=models.BooleanField(default=False, editable=False),
        ),
    ]
