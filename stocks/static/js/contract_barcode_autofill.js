(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        // ---- หน้า detail ของ CustomerProductContract (ไม่ใช่ inline) ----
        // เมื่อผู้ใช้เปลี่ยน barcode → auto-submit แบบ "Save and continue editing"

        var $barcodeMain = $('select[name="barcode"]');
        if ($barcodeMain.length) {
            // จำค่าเริ่มต้น ณ ตอน page load — ไม่ submit ถ้า value ไม่เปลี่ยน
            var initialVal = $barcodeMain.val();

            $barcodeMain.on('change', function () {
                var newVal = this.value;
                if (!newVal) return;
                if (newVal === initialVal) return; // ค่าเดิม ไม่ต้อง submit

                var $form = $(this).closest('form');
                if (!$form.find('input[name="_continue"]').length) {
                    $form.append('<input type="hidden" name="_continue" value="1">');
                }
                $form.submit();
            });
        }

        // ---- inline ใน Customer page ----
        // เมื่อเลือก barcode ใน row → ดึงชื่อสินค้ามาโชว์ทันทีทาง AJAX (ไม่ต้องรอ Save)
        $(document).on('change', 'select[name$="-barcode"]', function () {
            var val = this.value;
            var $row = $(this).closest('tr');
            var $td = $(this).closest('td');
            var $productCell = $row.find('.field-product');

            $td.find('.barcode-save-hint').remove();

            if (!val) return;

            $productCell.css('opacity', 0.5);
            $.get('/api/barcode-info/', {barcode_id: val})
                .done(function (data) {
                    if (!data || !data.product_name) return;
                    var $readonly = $productCell.find('.readonly');
                    if ($readonly.length) {
                        $readonly.text(data.product_name);
                    } else {
                        $productCell.text(data.product_name);
                    }
                })
                .always(function () {
                    $productCell.css('opacity', '');
                });
        });
    });

}());
