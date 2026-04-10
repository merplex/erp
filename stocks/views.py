import json
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from .models import DocumentLock
from . import line_webhook

# Create your views here.

@csrf_exempt
def line_webhook_view(request):
    if request.method != 'POST':
        return HttpResponse('ok')

    signature = request.headers.get('X-Line-Signature', '')
    body = request.body

    if not line_webhook.verify_signature(body, signature):
        return HttpResponse('invalid signature', status=403)

    try:
        data = json.loads(body)
        for event in data.get('events', []):
            line_webhook.handle_event(event)
    except Exception:
        pass

    return HttpResponse('ok')


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
