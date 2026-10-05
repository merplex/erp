import datetime

from django.test import TestCase

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
