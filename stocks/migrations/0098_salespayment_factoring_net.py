from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations, models
from django.db.models import Count, Max, Sum


def merge_factoring_transfers(apps, schema_editor):
    """แถวโอนแฟคตอริ่งเดิม (แยกทีละแถวรับเงิน/IV) -> จดยอดไว้ที่ SalesPayment.factoring_net
    แล้วสร้างรายการโอนรวม 1 รายการต่อบัญชีแฟคตอริ่งต่อวัน (เหมือน rebuild_factoring_transfers)"""
    BankTransaction = apps.get_model('stocks', 'BankTransaction')
    SalesPayment = apps.get_model('stocks', 'SalesPayment')
    BankAccount = apps.get_model('stocks', 'BankAccount')

    old = BankTransaction.objects.filter(source_type='FACTORING', factoring_payment__isnull=False)
    outs = old.filter(description__startswith='โอนเข้า ')
    for row in outs.values('factoring_payment_id').annotate(t=Sum('amount')):
        SalesPayment.objects.filter(pk=row['factoring_payment_id']).update(factoring_net=-row['t'])
    old.filter(models.Q(description__startswith='โอนเข้า ')
               | models.Q(description__startswith='รับโอนจากแฟคตอริ่ง ')).delete()

    accounts = {a.pk: a for a in BankAccount.objects.filter(account_type='FACTORING', linked_account__isnull=False)}
    groups = (SalesPayment.objects.exclude(factoring_net=0).filter(bank_account_id__in=list(accounts))
              .values('bank_account_id', 'payment_date').order_by()
              .annotate(total=Sum('factoring_net'), n=Count('id'),
                        customers=Count('order__customer', distinct=True), name=Max('order__customer__company_name')))
    for g in groups:
        fx = accounts[g['bank_account_id']]
        linked = BankAccount.objects.get(pk=fx.linked_account_id)
        net = Decimal(g['total']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        label = f"แฟคตอริ่ง {g['n']} รายการ"
        party = g['name'] if g['customers'] == 1 else ''
        out = BankTransaction.objects.create(
            bank_account_id=fx.pk, txn_date=g['payment_date'], amount=-net, source_type='FACTORING', party=party,
            description=f"โอนเข้า {linked.name}: {label}"[:255])
        BankTransaction.objects.create(
            bank_account_id=linked.pk, txn_date=g['payment_date'], amount=net, source_type='FACTORING', party=party,
            transfer_peer=out, description=f"รับโอนจากแฟคตอริ่ง {fx.name}: {label}"[:255])


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0097_factoring_fee_percent'),
    ]

    operations = [
        migrations.AddField(
            model_name='salespayment',
            name='factoring_net',
            field=models.DecimalField(decimal_places=4, default=0, editable=False, max_digits=18),
        ),
        migrations.RunPython(merge_factoring_transfers, migrations.RunPython.noop),
    ]
