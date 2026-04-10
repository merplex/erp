(function () {
    'use strict';

    function fetchBarcodeInfo(barcodeId, onSuccess) {
        fetch('/api/barcode-info/?barcode_id=' + encodeURIComponent(barcodeId))
            .then(function (r) { return r.json(); })
            .then(onSuccess)
            .catch(function () {});
    }

    function applyToRow(selectEl, data) {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$ || !data || !data.product_id) return;

        var $select = $(selectEl);

        // --- หา container ของ row (inline tr หรือ fieldset หน้า detail) ---
        var $container = $select.closest('tr');
        var isInline = $container.length > 0;
        if (!isInline) $container = $select.closest('fieldset, .form-row, form');

        // --- อัพเดท product field ---
        // หน้า detail: #id_product เป็น select2 ที่ต้อง set ผ่าน select2 API
        var $productSelect = isInline
            ? $container.find('select[name$="-product"]')
            : $('select[name="product"], #id_product');

        if ($productSelect.length && $productSelect.data('select2')) {
            // กรณี select2: สร้าง option ใหม่แล้ว trigger
            if (!$productSelect.find('option[value="' + data.product_id + '"]').length) {
                $productSelect.append(new Option(data.product_name, data.product_id, true, true));
            } else {
                $productSelect.val(data.product_id);
            }
            $productSelect.trigger('change');
        } else if ($productSelect.length) {
            $productSelect.val(data.product_id).trigger('change');
        }

        // --- อัพเดท/สร้าง unit info ใต้ barcode field ---
        var $unitEl = $container.find('.barcode-unit-display');
        if (!$unitEl.length) {
            $unitEl = $('<div class="barcode-unit-display" style="font-size:12px;color:#6b7280;margin-top:4px;"></div>');
            $select.closest('td, .field-barcode').append($unitEl);
        }
        var unit = data.unit_name || 'ชิ้น';
        var factor = data.conversion_factor || 1;
        var label = factor > 1 ? (unit + ' (' + factor + ' ชิ้น/หน่วย)') : unit;
        $unitEl.text(label);

        // --- แสดงชื่อสินค้าข้างๆ ถ้าเป็น readonly field ---
        var $productReadonly = isInline
            ? $container.find('.field-product .readonly')
            : $('.field-product .readonly');
        if ($productReadonly.length) {
            $productReadonly.text(data.product_name);
        }
    }

    function handleBarcodeChange(selectEl) {
        var val = selectEl.value;
        if (!val) return;
        fetchBarcodeInfo(val, function (data) {
            applyToRow(selectEl, data);
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        // ฟัง change บน select ของ barcode (ทั้ง main form และ inline)
        // Django admin autocomplete fires 'change' บน <select> เมื่อเลือกแล้ว
        $(document).on('change', 'select[name="barcode"], select[name$="-barcode"]', function () {
            handleBarcodeChange(this);
        });

        // รองรับ Unfold / Select2 ที่อาจ fire 'select2:select' แทน
        $(document).on('select2:select', 'select[name="barcode"], select[name$="-barcode"]', function () {
            handleBarcodeChange(this);
        });
    });

}());
