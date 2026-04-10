from django.db import migrations


def backfill_barcode(apps, schema_editor):
    CustomerProductContract = apps.get_model('stocks', 'CustomerProductContract')
    for contract in CustomerProductContract.objects.filter(barcode__isnull=True).select_related('product'):
        if not contract.product_id:
            continue
        # ใช้ barcode ล่าสุดของ product นั้น
        barcode = contract.product.barcodes.order_by('-created_at', '-id').first()
        if barcode:
            contract.barcode = barcode
            contract.save(update_fields=['barcode'])


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0043_customerproductcontract_barcode'),
    ]

    operations = [
        migrations.RunPython(backfill_barcode, migrations.RunPython.noop),
    ]
