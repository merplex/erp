(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        var $supplierField = $('#id_supplier');
        if (!$supplierField.length) return; // หน้านี้ไม่ใช่ PurchaseOrder add/change

        // ส่ง supplier_id ของ supplier ที่กำลังเลือกอยู่ในหน้า (ยังไม่ต้อง save)
        // แนบไปกับทุก request ไปยัง /admin/autocomplete/ ของช่อง product / barcode_obj ใน PurchaseItemInline
        // ให้ ProductAdmin.get_search_results (stocks/admin.py) กรองเฉพาะสินค้าที่ supplier นี้ขาย
        // + รายการที่ไม่ใช่สินค้า (ค่าบริการ) — ใช้ได้ทั้งหน้าเพิ่มใหม่และหน้าแก้ไข
        // ช่องสินค้า + ช่องบาร์โค้ด (ProductBarcodeAdmin.get_search_results กรองเหมือนกัน)
        var FIELDS = ['product', 'barcode_obj'];
        $.ajaxPrefilter(function (options) {
            if (!options.url || options.url.indexOf('/admin/autocomplete/') === -1) return;

            var supplierId = $supplierField.val();
            if (!supplierId) return;

            if (options.data && typeof options.data === 'object') {
                if (FIELDS.indexOf(options.data.field_name) === -1) return;
                options.data.supplier_id = supplierId;
            } else if (typeof options.data === 'string') {
                if (!FIELDS.some(function (f) { return options.data.indexOf('field_name=' + f + '&') !== -1
                        || options.data.slice(-('field_name=' + f).length) === 'field_name=' + f; })) return;
                options.data += '&supplier_id=' + encodeURIComponent(supplierId);
            } else if (FIELDS.some(function (f) { return new RegExp('[?&]field_name=' + f + '(&|$)').test(options.url); })) {
                var sep = options.url.indexOf('?') === -1 ? '?' : '&';
                options.url += sep + 'supplier_id=' + encodeURIComponent(supplierId);
            }
        });
    });

}());
