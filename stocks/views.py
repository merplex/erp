from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from .models import DocumentLock

# Create your views here.

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
