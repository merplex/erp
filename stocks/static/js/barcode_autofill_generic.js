(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        // ---- BOMIngredientInline / PurchaseItemInline / PurchaseReceiptLogInline ----
        // เมื่อเลือก barcode_obj ในแถว → auto-set ช่อง material/product ในแถวเดียวกันให้ตรงกันทันที
        // (ไม่ต้องรอ Save) ตรงกับ logic ฝั่ง server ที่ derive จาก barcode_obj เสมออยู่แล้ว
        $(document).on('change', 'select[name$="-barcode_obj"]', function () {
            var val = this.value;
            if (!val) return;

            var $row = $(this).closest('tr');
            var $targetSelect = $row.find('select[name$="-material"]');
            if (!$targetSelect.length) $targetSelect = $row.find('select[name$="-product"]');
            if (!$targetSelect.length) return;

            $.get('/api/barcode-info/', {barcode_id: val})
                .done(function (data) {
                    if (!data || !data.product_id) return;
                    if (String($targetSelect.val()) === String(data.product_id)) return;

                    var newOption = new Option(data.product_name, data.product_id, true, true);
                    $targetSelect.append(newOption).trigger('change');
                });
        });
    });

}());
