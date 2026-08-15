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
from stocks.views import unlock_document_view, line_webhook_view, line_webhook2_view, barcode_remaining_api, delivery_log_autosave, pending_barcodes_api, barcode_info_api, contract_update_barcode_api, stock_report_webview, purchase_quotation_price_api, sales_quotation_price_api, product_barcodes_api, product_bom_by_barcode_api, recommended_supplier_api

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/")),
    # ⚠️ ต้องอยู่ก่อน path("admin/", admin.site.urls) เสมอ — ตัวนั้น include() ทั้ง prefix
    # "admin/" ไปให้ Django admin's resolver จัดการเองทั้งหมด ถ้า route นี้อยู่หลัง จะไม่มีทาง
    # ถูก match เลย (Django admin เจอ "unlock-doc/" ไม่ตรง pattern ไหนของมันเอง ก็ 404 คืนไปเลย
    # โดยไม่ทันมาถึง path นี้) ยืนยันจาก console จริงที่เห็น POST .../admin/unlock-doc/ 404 ตลอด
    path("admin/unlock-doc/", unlock_document_view),
    path("admin/", admin.site.urls),
    path("api/barcode-remaining/", barcode_remaining_api),
    path("api/delivery-log/save/", delivery_log_autosave),
    path("api/pending-barcodes/", pending_barcodes_api),
    path("api/barcode-info/", barcode_info_api),
    path("api/contract/update-barcode/", contract_update_barcode_api),
    path("api/purchase-quotation-price/", purchase_quotation_price_api),
    path("api/sales-quotation-price/", sales_quotation_price_api),
    path("api/product-barcodes/", product_barcodes_api),
    path("api/product-bom-by-barcode/", product_bom_by_barcode_api),
    path("api/recommended-supplier/", recommended_supplier_api),
    path("webhook/line/", line_webhook_view),
    path("webhook/line2/", line_webhook2_view),
    path("report/stock/", stock_report_webview),
]
