class AdvanceOrderRunnerMiddleware:
    """เช็คทุกครั้งที่มีคนเข้าหน้า Admin ว่ามีกฎ AdvanceOrderRule (B7) ที่ถึงรอบสร้างเอกสารหรือยัง
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
        return self.get_response(request)
