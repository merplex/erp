import json
import os
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from .models import DocumentLock
from . import line_webhook


def _webhook_handler(request, secret_env, token_env):
    if request.method != 'POST':
        return HttpResponse('ok')

    secret = os.environ.get(secret_env, '')
    token = os.environ.get(token_env, '')
    signature = request.headers.get('X-Line-Signature', '')
    body = request.body

    if not line_webhook.verify_signature(body, signature, secret):
        import logging
        logger = logging.getLogger(__name__)
        logger.warning('LINE signature fail | secret_env=%s | secret_len=%d | sig=%s', secret_env, len(secret), signature[:20])
        return HttpResponse('invalid signature', status=403)

    try:
        data = json.loads(body)
        for event in data.get('events', []):
            line_webhook.handle_event(event, token)
    except Exception:
        pass

    return HttpResponse('ok')


@csrf_exempt
def line_webhook_view(request):
    """OA หลัก (ลูกค้า)"""
    return _webhook_handler(request, 'LINE_CHANNEL_SECRET', 'LINE_CHANNEL_ACCESS_TOKEN')


@csrf_exempt
def line_webhook2_view(request):
    """OA ส่วนตัว (Meebunholder Stock)"""
    return _webhook_handler(request, 'LINE2_CHANNEL_SECRET', 'LINE2_CHANNEL_ACCESS_TOKEN')


@staff_member_required
def barcode_remaining_api(request):
    """API: ตรวจสอบ barcode code ว่าอยู่ใน SO ไหน และเหลือส่งเท่าไร"""
    from .models import ProductBarcode, SalesItem
    so_id = request.GET.get('so_id', '').strip()
    code = request.GET.get('barcode', '').strip()

    if not so_id or not code:
        return JsonResponse({'valid': False})

    try:
        barcode = ProductBarcode.objects.select_related('product').get(code=code)
    except ProductBarcode.DoesNotExist:
        return JsonResponse({'valid': False, 'error': 'ไม่พบบาร์โค้ดนี้ในระบบ'})

    items = list(SalesItem.objects.filter(sales_order_id=so_id, barcode_obj=barcode)
                 .values('quantity_ordered', 'quantity_shipped'))
    if not items:
        return JsonResponse({'valid': False, 'error': 'บาร์โค้ดนี้ไม่อยู่ในรายการสั่งขายนี้'})

    total_ordered = sum(i['quantity_ordered'] or 0 for i in items)
    total_shipped = sum(i['quantity_shipped'] or 0 for i in items)
    remaining = max(0, total_ordered - total_shipped)

    return JsonResponse({
        'valid': True,
        'remaining': remaining,
        'product_name': barcode.product.name if barcode.product else '',
    })


@csrf_exempt
def unlock_document_view(request):
    if request.method == 'POST' and request.user.is_authenticated:
        ct_id = request.POST.get('content_type_id')
        obj_id = request.POST.get('object_id')
        if ct_id and obj_id:
            DocumentLock.objects.filter(
                content_type_id=ct_id,
                object_id=str(obj_id),
                user=request.user
            ).delete()
    return HttpResponse('ok')
