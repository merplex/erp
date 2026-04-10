"""
URL configuration for meebun_erp project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from stocks.views import unlock_document_view, line_webhook_view, line_webhook2_view, barcode_remaining_api, delivery_log_autosave, pending_barcodes_api

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/")),
    path("admin/", admin.site.urls),
    path("admin/unlock-doc/", unlock_document_view),
    path("api/barcode-remaining/", barcode_remaining_api),
    path("api/delivery-log/save/", delivery_log_autosave),
    path("api/pending-barcodes/", pending_barcodes_api),
    path("webhook/line/", line_webhook_view),
    path("webhook/line2/", line_webhook2_view),
]
