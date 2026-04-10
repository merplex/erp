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
def delivery_log_autosave(request):
    """Auto-save delivery log row via AJAX — ผลลัพธ์เหมือนกด Save"""
    if request.method != 'POST':
        return JsonResponse({'success': False}, status=405)

    from .models import ProductBarcode, SalesItem, SalesOrder, SalesDeliveryLog
    from django.utils import timezone as tz

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'error': 'invalid json'})

    so_id        = data.get('so_id')
    log_id       = data.get('log_id') or None
    barcode_code = (data.get('barcode_code') or '').strip()
    shipping_no  = (data.get('shipping_no') or '').strip()
    qty_raw      = data.get('quantity_shipped', '')
    notes        = (data.get('notes') or '').strip()
    shipped_date = (data.get('shipped_date') or '').strip()

    # validate SO
    try:
        so = SalesOrder.objects.get(pk=so_id)
    except (SalesOrder.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'ไม่พบ SO'})

    # validate barcode
    if not barcode_code:
        return JsonResponse({'success': False, 'error': 'กรุณากรอกรหัสบาร์โค้ด'})
    try:
        barcode = ProductBarcode.objects.select_related('product').get(code=barcode_code)
    except ProductBarcode.DoesNotExist:
        return JsonResponse({'success': False, 'errors': {'barcode_code': 'ไม่พบบาร์โค้ดนี้ในระบบ'}})
    if not SalesItem.objects.filter(sales_order=so, barcode_obj=barcode).exists():
        return JsonResponse({'success': False, 'errors': {'barcode_code': 'บาร์โค้ดนี้ไม่อยู่ในรายการสั่งขายนี้'}})

    # validate quantity
    try:
        qty = int(qty_raw)
        if qty < 0:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'errors': {'quantity_shipped': 'จำนวนต้องเป็นตัวเลขบวก'}})

    # parse shipped_date
    from django.utils.dateparse import parse_datetime, parse_date
    s_date = None
    if shipped_date:
        s_date = parse_datetime(shipped_date)
        if not s_date:
            d = parse_date(shipped_date)
            if d:
                s_date = tz.datetime(d.year, d.month, d.day, tzinfo=tz.get_current_timezone())
    if not s_date:
        s_date = tz.now()

    # get or create SalesDeliveryLog
    if log_id:
        try:
            log = SalesDeliveryLog.objects.get(pk=log_id, sales_order=so)
        except SalesDeliveryLog.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'ไม่พบ delivery log'})
        log.shipping_no     = shipping_no
        log.quantity_shipped = qty
        log.notes           = notes
        log.shipped_date    = s_date
        log.save()
    else:
        log = SalesDeliveryLog(
            sales_order      = so,
            barcode_obj      = barcode,
            shipping_no      = shipping_no,
            quantity_shipped = qty,
            notes            = notes,
            shipped_date     = s_date,
            user             = request.user,
        )
        log.save()  # model.save() จะ auto-set product + ลดสต็อก + อัพ quantity_shipped

    # คำนวณ remaining หลัง save
    items = SalesItem.objects.filter(sales_order=so, barcode_obj=barcode).values('quantity_ordered', 'quantity_shipped')
    total_ordered = sum(i['quantity_ordered'] or 0 for i in items)
    total_shipped = sum(i['quantity_shipped'] or 0 for i in items)
    remaining = max(0, total_ordered - total_shipped)

    return JsonResponse({
        'success': True,
        'log_id': log.pk,
        'remaining': remaining,
        'barcode_code': barcode.code,
    })


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
