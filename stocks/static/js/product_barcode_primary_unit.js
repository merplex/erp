(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        // ---- หน้าแก้ไขสินค้า: บาร์โค้ดแถวแรก (บาร์หลัก) ให้หน่วยตรงกับช่อง "หน่วย" ด้านบนเสมอ ----
        // แถวแรก = แถวบนสุดของ inline บาร์โค้ดเสมอ (เรียงตามลำดับที่เพิ่มไว้อยู่แล้ว)
        // บาร์โค้ดถัดไปยังกรอกหน่วยของตัวเองได้อิสระตามปกติ (เช่น 1 ถุง = 1.5234 kg)
        var $productUnit = $('#id_unit');
        if (!$productUnit.length) return;

        function syncPrimaryBarcodeUnit() {
            var $firstUnitInput = $('input[name$="-unit_name"]').first();
            if (!$firstUnitInput.length) return;
            $firstUnitInput.val($productUnit.val());
            $firstUnitInput.prop('readonly', true);
            $firstUnitInput.css({'background-color': '#f3f4f6', 'cursor': 'not-allowed'});
            $firstUnitInput.attr('title', 'หน่วยของบาร์โค้ดหลักจะตรงกับช่อง "หน่วย" ของสินค้าเสมอ');
        }

        syncPrimaryBarcodeUnit();
        $productUnit.on('change keyup input', syncPrimaryBarcodeUnit);
    });

}());
