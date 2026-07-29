from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Q

from stocks.models import SalesDeliveryLog


class Command(BaseCommand):
    help = (
        "คำนวณ dc_amount/rebate_amount ใหม่สำหรับใบส่งของ (SalesDeliveryLog/C6) เก่าที่ยัง"
        "ไม่ยืนยัน/ยังไม่จ่าย ตามสัญญา (T2 CustomerProductContract) ปัจจุบัน — ใช้แก้ยอดที่"
        "ค้าง 0 เพราะ save() ครั้งก่อนหน้ายังไม่มีสัญญา หรือสัญญาถูกแก้ทีหลัง"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="แสดงว่าจะแก้กี่แถว โดยไม่บันทึกจริง",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        logs = SalesDeliveryLog.objects.filter(
            Q(is_dc_confirmed=False) | Q(is_rebate_confirmed=False)
        ).select_related("sales_order__customer", "product")

        total = logs.count()
        updated = 0

        for log in logs:
            old_dc, old_rebate = log.dc_amount, log.rebate_amount
            log.sync_dc_rebate_from_contract()
            new_dc = old_dc if log.is_dc_confirmed else log.dc_amount
            new_rebate = old_rebate if log.is_rebate_confirmed else log.rebate_amount

            if new_dc != old_dc or new_rebate != old_rebate:
                updated += 1
                self.stdout.write(
                    f"#{log.pk} SO={log.sales_order.so_number} product={log.product} "
                    f"dc: {old_dc} -> {new_dc}  rebate: {old_rebate} -> {new_rebate}"
                )
                if not dry_run:
                    SalesDeliveryLog.objects.filter(pk=log.pk).update(
                        dc_amount=new_dc, rebate_amount=new_rebate
                    )

        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}ตรวจแล้ว {total} แถว (ยังไม่ยืนยัน DC หรือ Rebate) — แก้ไข {updated} แถว"
            )
        )
