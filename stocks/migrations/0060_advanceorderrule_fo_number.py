from django.db import migrations, models


def backfill_fo_number(apps, schema_editor):
    """เติมเลขที่เอกสารให้แถวเดิม (ถ้ามี) ที่สร้างไว้ก่อนเพิ่มฟิลด์นี้ — รูปแบบเดียวกับ generate_number()"""
    AdvanceOrderRule = apps.get_model('stocks', 'AdvanceOrderRule')
    counters = {}
    for rule in AdvanceOrderRule.objects.order_by('created_at', 'pk'):
        date_str = rule.created_at.strftime('%Y%m') if rule.created_at else '000000'
        counters[date_str] = counters.get(date_str, 0) + 1
        rule.fo_number = f"FO-{date_str}-{counters[date_str]:04d}"
        rule.save(update_fields=['fo_number'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0059_stockforecast_advanceorderrule'),
    ]

    operations = [
        migrations.AddField(
            model_name='advanceorderrule',
            name='fo_number',
            field=models.CharField(max_length=50, null=True, editable=False),
        ),
        migrations.RunPython(backfill_fo_number, noop_reverse),
        migrations.AlterField(
            model_name='advanceorderrule',
            name='fo_number',
            field=models.CharField(max_length=50, unique=True, editable=False),
        ),
    ]
