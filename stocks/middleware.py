class AdvanceOrderRunnerMiddleware:
    """เช็คทุกครั้งที่มีคนเข้าหน้า Admin ว่ามีกฎ AdvanceOrderRule (A6) ที่ถึงรอบสร้างเอกสารหรือยัง
    ระบบนี้ไม่มี Celery/cron จึงใช้ traffic ของหน้า Admin เองเป็นตัวกระตุ้นแทน scheduler ภายนอก"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'GET' and request.path.startswith('/admin/'):
            try:
                from .models import run_due_advance_orders
                run_due_advance_orders()
            except Exception:
                pass  # ห้ามให้ error ตรงนี้บัง page load เด็ดขาด
            try:
                from .models import run_due_loan_installments
                run_due_loan_installments()  # งวดผ่อนเงินกู้ที่ถึงกำหนด -> รายการเดินบัญชี (M3)
            except Exception:
                pass
            try:
                from .models import confirm_draft_sales_orders
                confirm_draft_sales_orders()  # SO ร่างที่เลยวันที่ใบแล้ว -> ยืนยัน (วันรุ่งขึ้น)
            except Exception:
                pass
            try:
                from .models import refresh_factored_payment_status
                refresh_factored_payment_status()  # ส่วนที่เหลือแฟคตอริ่งถึงวันรับ -> ขายแฟคตอริ่งแล้ว เป็นรับเงินครบแล้ว
            except Exception:
                pass
        return self.get_response(request)


class SubmitOnceMiddleware:
    """กันบันทึกซ้ำจากการกดซ้ำ / เน็ตช้าแล้วเบราว์เซอร์หรือ proxy ส่งฟอร์มเดิมซ้ำ (เช่น ขายแฟคตอริ่งเป็นกลุ่มแล้ว IV ซ้ำ)
    ทุกฟอร์ม POST ในหน้า Admin มีรหัส _once ประจำหน้า (js/submit_once.js) — คำขอแรกได้ทำงาน
    คำขอที่ส่งรหัสเดิมซ้ำ: รอคำขอแรกเสร็จ แล้วพากลับหน้าเดิมพร้อมแจ้งเตือน (ไม่ทำงานซ้ำ)
    คำขอแรกที่ไม่ได้บันทึก (ตอบหน้าเดิม เช่น ฟอร์มกรอกผิด/หน้ายืนยันของ action, หรือ error) คืนรหัสให้ส่งใหม่ได้"""
    WAIT_SECONDS = 45

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = ''
        if request.method == 'POST' and request.path.startswith('/admin/'):
            token = (request.POST.get('_once') or '')[:64]
        if not token:
            return self.get_response(request)
        from django.db import IntegrityError, transaction
        from .models import SubmitOnce
        try:
            with transaction.atomic():
                SubmitOnce.objects.create(token=token)
        except IntegrityError:
            return self._duplicate(request, token)
        try:
            response = self.get_response(request)
        except Exception:
            SubmitOnce.objects.filter(token=token).delete()
            raise
        if 300 <= response.status_code < 400:  # บันทึกสำเร็จ (Admin redirect หลังบันทึก)
            SubmitOnce.objects.filter(token=token).update(done=True)
        else:
            SubmitOnce.objects.filter(token=token).delete()
        SubmitOnce.cleanup()
        return response

    def _duplicate(self, request, token):
        import time
        from django.contrib import messages
        from django.http import HttpResponseRedirect
        from .models import SubmitOnce
        deadline = time.monotonic() + self.WAIT_SECONDS
        while time.monotonic() < deadline:
            done = SubmitOnce.objects.filter(token=token).values_list('done', flat=True).first()
            if done is None or done:  # คำขอแรกเสร็จแล้ว (บันทึก / ไม่ได้บันทึก)
                break
            time.sleep(0.5)
        messages.warning(request, "ระบบได้รับคำสั่งนี้ซ้ำ (กดซ้ำ หรือเน็ตส่งซ้ำ) — บันทึกครั้งเดียว ไม่บันทึกซ้ำ "
                                  "กรุณาตรวจผลในหน้านี้อีกครั้ง")
        return HttpResponseRedirect(request.get_full_path())
