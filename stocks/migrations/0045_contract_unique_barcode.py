from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0044_backfill_contract_barcode'),
    ]

    operations = [
        # ลบ unique_together เก่า (customer, product)
        migrations.AlterUniqueTogether(
            name='customerproductcontract',
            unique_together=set(),
        ),
        # เพิ่ม unique_together ใหม่ (customer, barcode)
        migrations.AlterUniqueTogether(
            name='customerproductcontract',
            unique_together={('customer', 'barcode')},
        ),
    ]
