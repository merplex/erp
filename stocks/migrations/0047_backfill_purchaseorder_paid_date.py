from django.db import migrations


def backfill_paid_date(apps, schema_editor):
    PurchaseOrder = apps.get_model('stocks', 'PurchaseOrder')
    PurchasePaymentLog = apps.get_model('stocks', 'PurchasePaymentLog')

    paid_orders = PurchaseOrder.objects.filter(payment_status='Paid', paid_date__isnull=True)
    for po in paid_orders:
        latest = PurchasePaymentLog.objects.filter(purchase_order=po).order_by('-payment_date').first()
        if latest:
            po.paid_date = latest.payment_date
            po.save(update_fields=['paid_date'])


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0046_purchasepaymentlog_payment_date_editable'),
    ]

    operations = [
        migrations.RunPython(backfill_paid_date, migrations.RunPython.noop),
    ]
