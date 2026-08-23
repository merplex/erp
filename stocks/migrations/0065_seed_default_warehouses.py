from django.db import migrations


def seed_warehouses(apps, schema_editor):
    Warehouse = apps.get_model('stocks', 'Warehouse')
    if not Warehouse.objects.filter(is_default=True).exists():
        Warehouse.objects.get_or_create(
            name='คลังสินค้าหลัก',
            defaults={'type': 'normal', 'is_default': True},
        )
    Warehouse.objects.get_or_create(
        name='คลังเศษเสีย',
        defaults={'type': 'scrap', 'is_default': False},
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0064_warehouse_stocktransfer_productstock'),
    ]

    operations = [
        migrations.RunPython(seed_warehouses, noop),
    ]
