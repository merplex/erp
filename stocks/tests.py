import datetime

from django.test import TestCase, override_settings

from .models import Customer, SalesOrder, SalesReceipt, generate_number


class DocumentNumberByDateTests(TestCase):
    """เดือนในเลขที่เอกสาร (SO/IV) ต้องตามวันที่ของเอกสาร ไม่ใช่วันที่กดบันทึก"""

    def setUp(self):
        self.customer = Customer.objects.create(company_name='C', contact_person='P', address='A', phone='0')

    def make_so(self, order_date):
        return SalesOrder.objects.create(customer=self.customer, order_date=order_date)

    def test_generate_number_uses_ref_date(self):
        self.assertEqual(generate_number('SO', SalesOrder, 'so_number', datetime.date(2026, 9, 21)),
                         'SO-202609-0001')

    def test_new_so_uses_order_date_month_and_continues_sequence(self):
        self.assertEqual(self.make_so(datetime.date(2026, 9, 1)).so_number, 'SO-202609-0001')
        self.assertEqual(self.make_so(datetime.date(2026, 10, 1)).so_number, 'SO-202610-0001')
        self.assertEqual(self.make_so(datetime.date(2026, 9, 30)).so_number, 'SO-202609-0002')

    def test_edit_order_date_to_other_month_renumbers_at_end(self):
        for _ in range(3):
            self.make_so(datetime.date(2026, 9, 5))
        so = self.make_so(datetime.date(2026, 10, 5))
        self.assertEqual(so.so_number, 'SO-202610-0001')
        so.order_date = datetime.date(2026, 9, 28)
        so.save()
        so.refresh_from_db()
        self.assertEqual(so.so_number, 'SO-202609-0004')

    def test_edit_within_same_month_keeps_number(self):
        so = self.make_so(datetime.date(2026, 9, 5))
        so.order_date = datetime.date(2026, 9, 20)
        so.save()
        self.assertEqual(so.so_number, 'SO-202609-0001')

    def test_legacy_mismatched_number_not_renumbered_on_plain_save(self):
        so = self.make_so(datetime.date(2026, 10, 5))
        SalesOrder.objects.filter(pk=so.pk).update(order_date=datetime.date(2026, 9, 5))
        so.refresh_from_db()
        so.save()
        self.assertEqual(so.so_number, 'SO-202610-0001')

    def test_receipt_uses_shipped_date_month(self):
        so = self.make_so(datetime.date(2026, 9, 1))
        r = SalesReceipt.objects.create(sales_order=so, shipped_date=datetime.date(2026, 9, 21))
        self.assertEqual(r.receipt_number, 'IV-202609-0001')


class BOMSelfReferenceCostTests(TestCase):
    """สูตร BOM ที่มีตัวสินค้าเอง (ตรงๆ หรือผ่านสูตรวัตถุดิบ) เป็นวัตถุดิบ ห้ามทำให้ต้นทุนวนคูณเพิ่มทุกครั้งที่คำนวณใหม่"""

    def setUp(self):
        from decimal import Decimal
        from .models import BOM, BOMIngredient, Product, ProductSupplier, Supplier
        self.Decimal, self.BOM, self.BOMIngredient = Decimal, BOM, BOMIngredient
        supplier = Supplier.objects.create(company_name='S', contact_person='P', address='A', phone='0')
        self.product = Product.objects.create(name='X', has_bom=True, sale_price=0)
        ProductSupplier.objects.create(product=self.product, supplier=supplier, latest_buy_price=Decimal('10'))
        self.product.refresh_from_db()

    def recalc_times(self, n):
        for _ in range(n):
            self.product.refresh_from_db()
            self.product.recalc_cost_and_price()
        self.product.refresh_from_db()

    def test_pack_bom_of_itself_does_not_inflate_cost(self):
        bom = self.BOM.objects.create(product=self.product, name='PACK12')
        self.BOMIngredient.objects.create(bom=bom, material=self.product, quantity=12)
        self.recalc_times(5)
        self.assertEqual(self.product.buy_price, self.Decimal('11.50'))  # Supplier 10 +15%
        self.assertEqual(self.product.cost_source, 'supplier')

    def test_indirect_cycle_does_not_inflate_cost(self):
        from .models import Product
        other = Product.objects.create(name='Y', has_bom=True, sale_price=0)
        bom_x = self.BOM.objects.create(product=self.product, name='BX')
        self.BOMIngredient.objects.create(bom=bom_x, material=other, quantity=2)
        bom_y = self.BOM.objects.create(product=other, name='BY')
        self.BOMIngredient.objects.create(bom=bom_y, material=self.product, quantity=2)
        for _ in range(5):
            other.refresh_from_db()
            other.recalc_cost_and_price()
            self.recalc_times(1)
        self.assertEqual(self.product.buy_price, self.Decimal('11.50'))

    def test_normal_bom_still_used(self):
        from .models import Product
        raw = Product.objects.create(name='R', buy_price=self.Decimal('20'), sale_price=0)
        bom = self.BOM.objects.create(product=self.product, name='B')
        self.BOMIngredient.objects.create(bom=bom, material=raw, quantity=1)
        self.recalc_times(3)
        self.assertEqual(self.product.buy_price, self.Decimal('20.00'))
        self.assertEqual(self.product.cost_source, 'bom')

    def test_inflated_price_resets_when_no_other_cost(self):
        # ไม่มีราคา Supplier และสูตรเดียวที่มีคือสูตรที่ใช้ตัวเอง (ห่วงตากผ้า 2.1 = ตัวเอง x1 + ลาเบล)
        from .models import Product
        product = Product.objects.create(name='H', has_bom=True, sale_price=0)
        label = Product.objects.create(name='L', buy_price=self.Decimal('0.50'), sale_price=0)
        bom = self.BOM.objects.create(product=product, name='H1')
        self.BOMIngredient.objects.create(bom=bom, material=product, quantity=1)
        self.BOMIngredient.objects.create(bom=bom, material=label, quantity=1)
        Product.objects.filter(pk=product.pk).update(
            buy_price=self.Decimal('9999999'), sale_price=self.Decimal('9999999'), cost_source='bom')
        product.refresh_from_db()
        product.recalc_cost_and_price()
        product.refresh_from_db()
        self.assertEqual(product.buy_price, 0)
        self.assertEqual(product.sale_price, 0)
        self.assertEqual(product.cost_source, 'supplier')


class ConfirmDraftSalesOrderTests(TestCase):
    """SO ร่าง -> ยืนยัน อัตโนมัติตั้งแต่วันรุ่งขึ้นของวันที่ใบ (ไม่แตะใบวันนี้/สถานะอื่น)"""

    def test_confirms_only_drafts_before_today(self):
        from . import models
        customer = Customer.objects.create(company_name='C', contact_person='P', address='A', phone='0')
        today = datetime.date(2026, 10, 8)
        old_draft = SalesOrder.objects.create(customer=customer, order_date=today - datetime.timedelta(days=1))
        new_draft = SalesOrder.objects.create(customer=customer, order_date=today)
        cancelled = SalesOrder.objects.create(customer=customer, order_date=today - datetime.timedelta(days=5))
        SalesOrder.objects.filter(pk=cancelled.pk).update(status='Cancelled')
        models._drafts_confirmed_on = None
        self.assertEqual(models.confirm_draft_sales_orders(today), 1)
        statuses = dict(SalesOrder.objects.values_list('pk', 'status'))
        self.assertEqual(statuses[old_draft.pk], 'Confirmed')
        self.assertEqual(statuses[new_draft.pk], 'Draft')
        self.assertEqual(statuses[cancelled.pk], 'Cancelled')


class PurchaseCurrencyTests(TestCase):
    """ราคา Supplier / ใบสั่งซื้อ / การจ่ายเงิน สกุลต่างประเทศ: ต้นทุนและสมุดบัญชีเป็นบาท = ยอด x เรท"""

    def setUp(self):
        from decimal import Decimal
        from .models import Product, ProductSupplier, PurchaseOrder, Supplier
        self.D = Decimal
        self.cn = Supplier.objects.create(company_name='CN', contact_person='P', address='A', phone='0',
                                          type='International')
        self.th = Supplier.objects.create(company_name='TH', contact_person='P', address='A', phone='0')
        self.product = Product.objects.create(name='X', sale_price=0)
        ProductSupplier.objects.create(product=self.product, supplier=self.cn, latest_buy_price=Decimal('10'),
                                       currency='RMB', exchange_rate=Decimal('5.2'))
        ProductSupplier.objects.create(product=self.product, supplier=self.th, latest_buy_price=Decimal('50'),
                                       currency='THB', exchange_rate=Decimal('9'))
        self.po = PurchaseOrder.objects.create(supplier=self.cn, currency='RMB', exchange_rate=Decimal('5'))

    def test_cost_compares_supplier_prices_in_baht(self):
        from .models import ProductSupplier
        self.product.refresh_from_db()
        self.assertEqual(ProductSupplier.objects.get(supplier=self.th).exchange_rate, 1)  # บาท = เรท 1
        self.assertEqual(self.product.auto_cost, self.D('59.80'))  # RMB 10 x 5.2 = 52 > 50 -> +15%

    def test_po_item_price_and_payment_ledger_in_baht(self):
        from .models import BankTransaction, PurchaseItem, PurchasePaymentLog
        PurchaseItem.objects.create(purchase_order=self.po, product=self.product, quantity_unit=100, unit_price=0)
        self.assertEqual(self.po.items.get().unit_price, self.D('10.00'))  # ราคา Supplier สกุลเดียวกับใบ
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):  # สกุลต่างประเทศ ไม่กรอกเรท = บันทึกไม่ได้ (ไม่ใช้เรทของใบแทน)
            PurchasePaymentLog.objects.create(purchase_order=self.po, amount=self.D('400'))
        pay_default = PurchasePaymentLog.objects.create(purchase_order=self.po, amount=self.D('400'),
                                                        exchange_rate=self.D('5'))
        pay_custom = PurchasePaymentLog.objects.create(purchase_order=self.po, amount=self.D('100'),
                                                       exchange_rate=self.D('5.3'))
        amounts = dict(BankTransaction.objects.filter(purchase_payment__isnull=False)
                       .values_list('purchase_payment_id', 'amount'))
        self.assertEqual(amounts[pay_default.pk], self.D('-2000'))
        self.assertEqual(amounts[pay_custom.pk], self.D('-530'))
        self.po.refresh_from_db()
        self.assertEqual(self.po.payment_status, 'Partial')  # เทียบยอดเป็น RMB: จ่าย 500 จาก 1,000
        self.assertEqual(self.po.balance_due, self.D('500'))

    def test_item_price_converted_when_supplier_price_in_other_currency(self):
        from .models import PurchaseItem, PurchaseOrder
        po_usd = PurchaseOrder.objects.create(supplier=self.th, currency='USD', exchange_rate=self.D('35'))
        PurchaseItem.objects.create(purchase_order=po_usd, product=self.product, quantity_unit=1, unit_price=0)
        self.assertEqual(po_usd.items.get().unit_price, self.D('1.43'))  # 50 บาท / 35

    def test_currency_warnings_and_missing_rate(self):
        from .admin import PurchaseOrderAdminForm
        from .models import Product, ProductSupplier, po_currency_warnings
        thb_item = Product.objects.create(name='Y', sale_price=0)
        ProductSupplier.objects.create(product=thb_item, supplier=self.cn, latest_buy_price=self.D('30'))
        self.assertEqual(po_currency_warnings('RMB', self.cn.pk, [self.product.pk]), [])
        self.assertIn('หลายสกุลเงิน', po_currency_warnings('RMB', self.cn.pk, [self.product.pk, thb_item.pk])[0])
        self.assertIn('แต่ใบสั่งซื้อเป็น', po_currency_warnings('USD', self.cn.pk, [self.product.pk])[0])
        base = {'supplier': self.cn.pk, 'order_date': '2026-10-08', 'vat_percent': '0', 'invoice_no_supplier': '',
                'status': 'Pending', 'payment_status': 'Unpaid'}
        form = PurchaseOrderAdminForm(data={**base, 'currency': 'RMB', 'exchange_rate': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('exchange_rate', form.errors)
        form = PurchaseOrderAdminForm(data={**base, 'currency': 'RMB', 'exchange_rate': '5.1'})
        self.assertTrue(form.is_valid(), form.errors)
        form = PurchaseOrderAdminForm(data={**base, 'currency': 'THB', 'exchange_rate': ''})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['exchange_rate'], 1)

    @override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                                 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
    def test_settle_action_rejects_mixed_currency_and_uses_entered_rate(self):
        import datetime
        from django.contrib.auth.models import User
        from django.test import Client
        from .models import BankTransaction, PurchaseItem, PurchaseOrder, PurchasePaymentLog
        user = User.objects.create_superuser('admin', 'a@a.a', 'x')
        client = Client()
        client.force_login(user)
        PurchaseItem.objects.create(purchase_order=self.po, product=self.product, quantity_unit=100, unit_price=self.D('10'))
        po_thb = PurchaseOrder.objects.create(supplier=self.th)
        PurchaseItem.objects.create(purchase_order=po_thb, product=self.product, quantity_unit=1, unit_price=self.D('50'))
        url = '/admin/stocks/financereport/'
        data = {'action': 'settle_and_close_orders', 'apply': '1', 'payment_date': datetime.date(2026, 10, 8)}
        client.post(url, {**data, '_selected_action': [self.po.pk, po_thb.pk]}, HTTP_HOST='localhost')
        self.assertFalse(PurchasePaymentLog.objects.exists())  # คนละสกุลเงิน จ่ายรวมไม่ได้
        client.post(url, {**data, '_selected_action': [self.po.pk]}, HTTP_HOST='localhost')
        self.assertFalse(PurchasePaymentLog.objects.exists())  # RMB ไม่กรอกเรท จ่ายไม่ได้
        client.post(url, {**data, '_selected_action': [self.po.pk], 'exchange_rate': '5.3'}, HTTP_HOST='localhost')
        pay = PurchasePaymentLog.objects.get()
        self.assertEqual((pay.amount, pay.exchange_rate), (self.D('1000'), self.D('5.3')))
        self.assertEqual(BankTransaction.objects.get(purchase_payment=pay).amount, self.D('-5300'))


class ReceivePaymentActionTests(TestCase):
    """A1/A2 action รับเงินตามยอดค้าง: มีคอลัมน์ยอดค้างชำระ + กรอกยอดที่จะรับเองได้ (ค่าเริ่มต้น = ยอดค้าง)"""

    def setUp(self):
        from decimal import Decimal
        from django.contrib.auth.models import User
        from .models import BankAccount
        self.Decimal = Decimal
        self.client.force_login(User.objects.create_superuser('admin', 'a@a.com', 'x'))
        self.bank = BankAccount.objects.create(name='B')
        customer = Customer.objects.create(company_name='C', contact_person='P', address='A', phone='0')
        so = SalesOrder.objects.create(customer=customer, order_date=datetime.date(2026, 9, 1))
        self.receipt = SalesReceipt.objects.create(sales_order=so, shipped_date=datetime.date(2026, 9, 21),
                                                   due_date=datetime.date(2026, 11, 2))
        SalesReceipt.objects.filter(pk=self.receipt.pk).update(grand_total=Decimal('1000'))
        self.url = '/admin/stocks/salesreceipt/'

    def post(self, amount=None, apply=True):
        data = {'action': 'receive_payment', '_selected_action': [self.receipt.pk]}
        if apply:
            data.update({'apply': '1', 'bank_account': self.bank.pk, 'payment_date': '2026-10-09'})
            if amount is not None:
                data[f'amount_{self.receipt.pk}'] = amount
        return self.client.post(self.url, data)

    def payments(self):
        from .models import SalesPayment
        return list(SalesPayment.objects.filter(receipt=self.receipt).values_list('amount', flat=True))

    def test_confirm_page_shows_outstanding_and_default_input(self):
        resp = self.post(apply=False)
        self.assertContains(resp, 'ยอดค้างชำระ')
        self.assertContains(resp, f'name="amount_{self.receipt.pk}"')
        self.assertContains(resp, 'value="1,000.00"')

    def test_partial_amount(self):
        self.assertEqual(self.post('400.50').status_code, 302)
        self.assertEqual(self.payments(), [self.Decimal('400.50')])

    def test_comma_amount(self):
        self.post('1,000.00')
        self.assertEqual(self.payments(), [self.Decimal('1000.00')])

    def test_bad_inputs_rerender_without_saving(self):
        for bad in ['abc', '-5', '1000.01', '1.234', 'NaN', 'Infinity', '1e999', '-1e999', '1e-999']:
            resp = self.post(bad)
            self.assertEqual(resp.status_code, 200, bad)
            self.assertContains(resp, 'ยอดที่จะรับไม่ถูกต้อง')
        self.assertEqual(self.payments(), [])

    def test_blank_or_zero_skips(self):
        for v in ['', '0']:
            self.assertEqual(self.post(v).status_code, 302)
        self.assertEqual(self.payments(), [])

    def test_multiple_receipts_merge_into_one_bank_row(self):
        from .models import BankTransaction, SalesPayment
        second = SalesReceipt.objects.create(sales_order=self.receipt.sales_order,
                                             shipped_date=datetime.date(2026, 9, 22))
        SalesReceipt.objects.filter(pk=second.pk).update(grand_total=self.Decimal('500'))
        self.client.post(self.url, {
            'action': 'receive_payment', '_selected_action': [self.receipt.pk, second.pk], 'apply': '1',
            'bank_account': self.bank.pk, 'payment_date': '2026-10-09',
            f'amount_{self.receipt.pk}': '300', f'amount_{second.pk}': '500'})
        refs = set(SalesPayment.objects.values_list('batch_ref', flat=True))
        self.assertEqual(len(refs), 1)
        self.assertNotEqual(refs, {''})
        rows = BankTransaction.objects.filter(bank_account=self.bank)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get().amount, self.Decimal('800'))


class PayPurchaseActionTests(TestCase):
    """A3 action ชำระ: แยกราย PO + ยอดของใบ/ยอดค้างจ่าย/ยอดที่จะจ่าย (แก้ได้) + เรทกรอกครั้งเดียว ห้ามปนสกุลเงิน"""

    def setUp(self):
        from decimal import Decimal
        from django.contrib.auth.models import User
        from .models import BankAccount, Product, PurchaseItem, PurchaseOrder, Supplier
        self.Decimal = Decimal
        self.client.force_login(User.objects.create_superuser('admin', 'a@a.com', 'x'))
        self.bank = BankAccount.objects.create(name='B', is_default=True)
        self.supplier = Supplier.objects.create(company_name='S', contact_person='P', address='A', phone='0')
        self.product = Product.objects.create(name='X', sale_price=0)
        self.PurchaseOrder, self.PurchaseItem = PurchaseOrder, PurchaseItem
        self.url = '/admin/stocks/financereport/'

    def make_po(self, total, currency='THB', rate='1'):
        po = self.PurchaseOrder.objects.create(supplier=self.supplier, currency=currency,
                                               exchange_rate=self.Decimal(rate), vat_percent=0)
        item = self.PurchaseItem.objects.create(purchase_order=po, product=self.product, quantity_ordered=1)
        self.PurchaseItem.objects.filter(pk=item.pk).update(unit_price=self.Decimal(total))
        return po

    def post(self, pos, amounts=None, apply=True, **extra):
        data = {'action': 'settle_and_close_orders', '_selected_action': [p.pk for p in pos]}
        if apply:
            data.update({'apply': '1', 'bank_account': self.bank.pk, 'payment_date': '2026-10-09', **extra})
            for po, amount in (amounts or {}).items():
                data[f'amount_{po.pk}'] = amount
        return self.client.post(self.url, data)

    def paid(self, po):
        return list(po.payment_logs.values_list('amount', flat=True))

    def test_confirm_page_lists_each_po(self):
        a, b = self.make_po('1000'), self.make_po('250.50')
        resp = self.post([a, b], apply=False)
        for text in ('ยอดของใบ', 'ยอดค้างจ่าย', 'ยอดที่จะจ่าย', a.po_number, b.po_number,
                     'type="date" name="payment_date"', 'วันที่จ่ายเงิน',
                     f'name="amount_{a.pk}"', 'value="1,000.00"', 'value="250.50"'):
            self.assertContains(resp, text)

    def test_partial_and_skip_per_po(self):
        from .models import BankTransaction
        a, b, c = self.make_po('1000'), self.make_po('500'), self.make_po('300')
        resp = self.post([a, b, c], {a: '400', b: '500', c: ''})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.paid(a), [self.Decimal('400')])
        self.assertEqual(self.paid(b), [self.Decimal('500')])
        self.assertEqual(self.paid(c), [])
        a.refresh_from_db(); b.refresh_from_db(); c.refresh_from_db()
        self.assertEqual((a.payment_status, b.payment_status, c.payment_status), ('Partial', 'Paid', 'Unpaid'))
        rows = BankTransaction.objects.filter(bank_account=self.bank)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get().amount, self.Decimal('-900'))
        # รอบต่อไป: ยอดค้างจ่ายของใบ a = 600
        self.assertContains(self.post([a], apply=False), 'value="600.00"')

    def test_bad_inputs_rerender_without_saving(self):
        a = self.make_po('1000')
        for bad in ['abc', '-5', '1000.01', '1.234', 'NaN', '1e999']:
            resp = self.post([a], {a: bad})
            self.assertEqual(resp.status_code, 200, bad)
            self.assertContains(resp, 'ยอดที่จะจ่ายไม่ถูกต้อง')
        self.assertEqual(self.paid(a), [])

    def test_mixed_currency_blocked(self):
        a, b = self.make_po('1000'), self.make_po('100', 'CNY', '5')
        resp = self.post([a, b], apply=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.paid(a) + self.paid(b), [])

    def test_foreign_currency_needs_rate_and_books_thb(self):
        from .models import BankTransaction
        a, b = self.make_po('100', 'CNY', '5'), self.make_po('50', 'CNY', '5')
        resp = self.post([a, b], {a: '100', b: '20'})
        self.assertEqual(resp.status_code, 200)  # ไม่กรอกเรท
        self.assertEqual(self.paid(a), [])
        self.post([a, b], {a: '100', b: '20'}, exchange_rate='5.1')
        self.assertEqual(self.paid(a), [self.Decimal('100')])
        self.assertEqual(self.paid(b), [self.Decimal('20')])
        self.assertEqual(BankTransaction.objects.get(bank_account=self.bank).amount, self.Decimal('-612'))

    def test_action_label(self):
        self.make_po('10')
        resp = self.client.get(self.url)
        self.assertContains(resp, 'ชำระเงิน (Payment)')
        self.assertNotContains(resp, 'ชำระครบ/ปิดยอด')


class IncomeReportActionsTests(TestCase):
    def test_a4_has_no_full_settle_action(self):
        from django.contrib.auth.models import User
        self.client.force_login(User.objects.create_superuser('admin', 'a@a.com', 'x'))
        resp = self.client.get('/admin/stocks/incomereport/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'ชำระครบ/ปิดยอด')
        self.assertContains(resp, 'ปิดยอดกรณีพิเศษ')
