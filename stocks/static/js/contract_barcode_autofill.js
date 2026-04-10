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
        // เมื่อเลือก barcode ใน row → แสดง hint ให้ผู้ใช้กด Save
        $(document).on('change', 'select[name$="-barcode"]', function () {
            var val = this.value;
            if (!val) return;

            var $td = $(this).closest('td');
            if (!$td.find('.barcode-save-hint').length) {
                $td.append(
                    '<div class="barcode-save-hint" style="font-size:11px;color:#2563eb;margin-top:3px;">กด Save เพื่อแสดงชื่อสินค้า</div>'
                );
            }
        });
    });

}());
