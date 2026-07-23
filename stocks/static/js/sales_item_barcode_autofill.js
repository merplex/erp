(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        // ---- SalesItemInline (รายการที่จะขาย) ----
        // เมื่อเลือก barcode_obj ใน row → auto-set ช่อง product ให้ตรงกันทันที (ไม่ต้องรอ Save)
        // ตรงกับ logic ฝั่ง server (SalesItem.save()) ที่ derive product จาก barcode_obj เสมออยู่แล้ว
        $(document).on('change', 'select[name$="-barcode_obj"]', function () {
            var val = this.value;
            if (!val) return;

            var $row = $(this).closest('tr');
            var $productSelect = $row.find('select[name$="-product"]');
            if (!$productSelect.length) return;

            $.get('/api/barcode-info/', {barcode_id: val})
                .done(function (data) {
                    if (!data || !data.product_id) return;
                    if (String($productSelect.val()) === String(data.product_id)) return;
                    var newOption = new Option(data.product_name, data.product_id, true, true);
                    $productSelect.append(newOption).trigger('change');
                });
        });
    });

}());
