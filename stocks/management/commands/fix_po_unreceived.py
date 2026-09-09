from django.core.management.base import BaseCommand
from django.db.models import Sum, F

from stocks.models import PurchaseOrder


class Command(BaseCommand):
    help = (
        "หาใบสั่งซื้อ (B1) ที่สถานะเป็น Completed/ปิดงาน ทั้งที่ยอดรับของยังไม่ครบ "
        "แล้วคำนวณสถานะใหม่จากยอดรับจริง (update_status). ค่าเริ่มต้นเป็น dry-run "
        "ต้องใส่ --yes ถึงจะบันทึกจริง"
    )

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="บันทึกจริง (ไม่ใส่ = แค่แสดงรายการ)")
        parser.add_argument(
            "--po",
            action="append",
            default=None,
            help="ระบุเลขที่ PO เจาะจง (ใส่ซ้ำได้). ไม่ใส่ = ตรวจทุกใบที่เข้าเงื่อนไข",
        )

    def handle(self, *args, **options):
        commit = options["yes"]
        only = options["po"]

        qs = PurchaseOrder.objects.filter(status="Completed").annotate(
            _ord=Sum("items__quantity_ordered"),
            _rec=Sum("items__quantity_received"),
        ).filter(_ord__gt=0, _rec__lt=F("_ord"))
        if only:
            qs = qs.filter(po_number__in=only)

        rows = list(qs.order_by("order_date"))
        if not rows:
            self.stdout.write(self.style.SUCCESS("ไม่พบใบสั่งซื้อที่ปิดงานทั้งที่รับของไม่ครบ"))
            return

        for po in rows:
            before = po.status
            if commit:
                po.update_status()
                po.refresh_from_db()
                after = po.status
            else:
                after = "(dry-run)"
            self.stdout.write(
                f"{po.po_number}  order_date={po.order_date}  "
                f"ordered={po._ord} received={po._rec or 0}  {before} -> {after}"
            )

        prefix = "" if commit else "[DRY RUN — ใส่ --yes เพื่อบันทึก] "
        self.stdout.write(self.style.SUCCESS(f"{prefix}ทั้งหมด {len(rows)} ใบ"))
