import json
import os
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
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
