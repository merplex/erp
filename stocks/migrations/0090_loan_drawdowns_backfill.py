from django.db import migrations


def move_principal_to_drawdowns(apps, schema_editor):
    """เงินกู้เดิม (ยอดกู้ก้อนเดียว) -> รับเงินต้น 1 ครั้งตามวันที่รับเงินกู้ แล้วย้ายรายการรับเงินในสมุดมาผูกกับก้อนนั้น"""
    Loan = apps.get_model('stocks', 'Loan')
    LoanDrawdown = apps.get_model('stocks', 'LoanDrawdown')
    BankTransaction = apps.get_model('stocks', 'BankTransaction')
    for loan in Loan.objects.all():
        if not loan.principal or loan.principal <= 0 or not loan.loan_date:
            continue
        drawdown = LoanDrawdown.objects.create(loan=loan, draw_date=loan.loan_date, amount=loan.principal)
        BankTransaction.objects.filter(loan_disbursement=loan).update(loan_drawdown=drawdown,
                                                                      loan_disbursement=None)


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0089_loan_drawdowns'),
    ]

    operations = [
        migrations.RunPython(move_principal_to_drawdowns, migrations.RunPython.noop),
    ]
