from django.db import migrations
from decimal import Decimal


def backfill_auto_cost(apps, schema_editor):
    Product = apps.get_model('stocks', 'Product')
    ProductSupplier = apps.get_model('stocks', 'ProductSupplier')

    for product in Product.objects.all():
        best = (
            ProductSupplier.objects
            .filter(product=product, latest_buy_price__gt=0)
            .order_by('-latest_buy_price')
            .first()
        )
        if best:
            auto_cost = (best.latest_buy_price * Decimal('1.15')).quantize(Decimal('0.01'))
            manual = product.manual_buy_price or Decimal('0')
            effective = manual if manual > 0 else auto_cost
            Product.objects.filter(pk=product.pk).update(
                auto_cost=auto_cost,
                buy_price=effective,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0048_add_auto_cost_and_manual_buy_price'),
    ]

    operations = [
        migrations.RunPython(backfill_auto_cost, migrations.RunPython.noop),
    ]
