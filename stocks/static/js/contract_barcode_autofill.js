(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        // ---- หน้า detail ของ CustomerProductContract (ไม่ใช่ inline) ----
        // เมื่อเลือก barcode → auto-submit แบบ "Save and continue editing"
        // หน้าจะ reload กลับมาพร้อม product + unit info ที่ถูก set โดย save_model

        var $barcodeMain = $('select[name="barcode"]');
        if ($barcodeMain.length) {
            $barcodeMain.on('change', function () {
                var val = this.value;
                if (!val) return;

                var $form = $(this).closest('form');
                // เพิ่ม hidden field _continue → Django จะ save แล้วกลับมาหน้าเดิม
                if (!$form.find('input[name="_continue"]').length) {
                    $form.append('<input type="hidden" name="_continue" value="1">');
                }
                // submit ทันที
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
