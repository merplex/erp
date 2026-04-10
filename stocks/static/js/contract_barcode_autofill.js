(function () {
    'use strict';

    // API: ดึงข้อมูล barcode (product + unit) จาก code
    function fetchBarcodeInfo(barcodeId, callback) {
        fetch('/api/barcode-info/?barcode_id=' + encodeURIComponent(barcodeId))
            .then(function (r) { return r.json(); })
            .then(callback)
            .catch(function () {});
    }

    // อัพเดท product field (readonly text) และ unit info ใน row เดียวกัน
    function applyBarcodeToRow(barcodeSelectEl) {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        var $select = $(barcodeSelectEl);
        var val = $select.val();
        if (!val) return;

        fetchBarcodeInfo(val, function (data) {
            if (!data || !data.product_id) return;

            var $row = $select.closest('tr, .form-row, fieldset');

            // --- อัพเดท product hidden + display ---
            // ในหน้า detail (ไม่ใช่ inline): หา select#id_product
            var $productSelect = $row.find('select[name$="-product"], select[id$="id_product"]');
            if (!$productSelect.length) {
                $productSelect = $('#id_product');
            }
            if ($productSelect.length) {
                // ถ้า select มี option นั้น → เลือก
                if ($productSelect.find('option[value="' + data.product_id + '"]').length) {
                    $productSelect.val(data.product_id).trigger('change');
                } else {
                    // เพิ่ม option ใหม่แล้วเลือก (กรณี select2 / django autocomplete)
                    var opt = new Option(data.product_name, data.product_id, true, true);
                    $productSelect.append(opt).trigger('change');
                }
            }

            // --- อัพเดท unit info span ---
            var $unitSpan = $row.find('.barcode-unit-info');
            if (!$unitSpan.length) {
                $unitSpan = $('<span class="barcode-unit-info" style="font-size:12px;color:#6b7280;margin-left:8px;white-space:nowrap;"></span>');
                $select.closest('td, .field-barcode').append($unitSpan);
            }
            var unit = data.unit_name || 'ชิ้น';
            var factor = data.conversion_factor || 1;
            if (factor > 1) {
                $unitSpan.text(unit + ' (' + factor + ' ชิ้น/หน่วย)');
            } else {
                $unitSpan.text(unit);
            }
        });
    }

    function initContractPage() {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        // หน้า detail: ฟัง change บน barcode select
        $(document).on('change', 'select[name="barcode"], select[id="id_barcode"]', function () {
            applyBarcodeToRow(this);
        });

        // inline rows: ฟัง change บน barcode autocomplete ทุก row
        $(document).on('change', 'select[name*="-barcode"]', function () {
            applyBarcodeToRow(this);
        });

        // Django select2: autocomplete fires 'select2:select'
        $(document).on('select2:select', function (e) {
            var name = (e.target && e.target.name) || '';
            if (name === 'barcode' || name.indexOf('-barcode') !== -1) {
                applyBarcodeToRow(e.target);
            }
        });
    }

    document.addEventListener('DOMContentLoaded', initContractPage);

}());
