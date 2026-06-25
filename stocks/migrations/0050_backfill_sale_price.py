from django.db import migrations
from decimal import Decimal


def backfill_sale_price(apps, schema_editor):
    Product = apps.get_model('stocks', 'Product')
    CustomerProductContract = apps.get_model('stocks', 'CustomerProductContract')

    for product in Product.objects.filter(buy_price__gt=0):
        min_sale = (product.buy_price * Decimal('1.15')).quantize(Decimal('0.01'))

        lowest_contract = (
            CustomerProductContract.objects
            .filter(product=product, contract_price__gt=0)
            .order_by('contract_price')
            .first()
        )
        contract_price = lowest_contract.contract_price if lowest_contract else Decimal('0')
        new_sale = max(min_sale, contract_price)

        if new_sale != product.sale_price:
            Product.objects.filter(pk=product.pk).update(sale_price=new_sale)


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0049_backfill_auto_cost'),
    ]

    operations = [
        migrations.RunPython(backfill_sale_price, migrations.RunPython.noop),
    ]
