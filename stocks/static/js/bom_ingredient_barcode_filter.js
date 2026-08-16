(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        // ---- BOMIngredientInline: จำกัดตัวเลือก barcode_obj ให้เห็นเฉพาะบาร์โค้ดของวัตถุดิบแถวนั้นๆ ----
        // Select2 ของ barcode_obj เป็น autocomplete field (ค้นหาผ่าน /admin/autocomplete/)
        // เราจำ material_id ของแถวที่กำลังเปิด dropdown ไว้ก่อนยิง request แล้วแนบไปกับทุก request
        // ให้ ProductBarcodeAdmin.get_search_results (stocks/admin.py) กรองเฉพาะบาร์โค้ดของวัตถุดิบนั้น
        var activeMaterialId = '';

        $(document).on('select2:opening', 'select[name$="-barcode_obj"]', function () {
            var $row = $(this).closest('tr');
            activeMaterialId = $row.find('select[name$="-material"]').val() || '';
        });

        $.ajaxPrefilter(function (options) {
            if (!options.url || options.url.indexOf('/admin/autocomplete/') === -1) return;
            if (!activeMaterialId) return;

            if (options.data && typeof options.data === 'object') {
                if (options.data.field_name !== 'barcode_obj') return;
                options.data.material_id = activeMaterialId;
            } else if (typeof options.data === 'string') {
                if (options.data.indexOf('field_name=barcode_obj') === -1) return;
                options.data += '&material_id=' + encodeURIComponent(activeMaterialId);
            }
        });

        // ---- เลือก/เปลี่ยนวัตถุดิบ → เติมบาร์โค้ดหลัก (ตัวแรกที่เพิ่มไว้) ให้อัตโนมัติ ----
        // ถ้ามีบาร์โค้ดเดียว = เลือกให้เลย, ถ้ามีหลายบาร์ = เลือกตัวหลักเป็น default (ยังกดเปลี่ยนได้)
        $(document).on('change', 'select[name$="-material"]', function () {
            var materialId = this.value;
            var $row = $(this).closest('tr');
            var $barcodeSelect = $row.find('select[name$="-barcode_obj"]');
            if (!$barcodeSelect.length) return;

            // เคลียร์บาร์โค้ดเดิมทิ้งก่อนเสมอ เพราะบาร์เก่าอาจไม่ใช่ของวัตถุดิบตัวใหม่แล้ว
            $barcodeSelect.val(null).trigger('change');
            if (!materialId) return;

            $.get('/api/product-barcodes/', {product_id: materialId}).done(function (data) {
                var items = (data && data.items) || [];
                if (!items.length) return;
                var primary = items[0]; // บาร์หลัก = บาร์โค้ดแรกที่เพิ่มไว้ให้วัตถุดิบนี้
                var label = primary.code + (primary.unit_name ? ' (' + primary.unit_name + ')' : '');
                var newOption = new Option(label, primary.id, true, true);
                $barcodeSelect.append(newOption).trigger('change');
            });
        });
    });

}());
