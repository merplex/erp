(function () {
    'use strict';

    // ---- inline ที่มีทั้ง "สินค้า/วัตถุดิบ" และ "บาร์โค้ด" ในแถวเดียวกัน (SO, PO, BOM, ใบเสนอราคา ฯลฯ) ----
    // เปลี่ยนบาร์โค้ด -> สินค้าเป็นของบาร์โค้ดนั้น / เปลี่ยนสินค้า -> บาร์โค้ดหลักของสินค้าใหม่
    // (ถ้าบาร์โค้ดที่เลือกอยู่เป็นของสินค้านั้นอยู่แล้ว ไม่แตะ -> ไม่วนกันเองและไม่ทับตัวที่ผู้ใช้เลือก)
    var PRODUCT_SEL = 'select[name$="-product"], select[name$="-material"]';
    var BARCODE_SEL = 'select[name$="-barcode_obj"], select[name$="-barcode"]';

    function setSelect($select, id, text) {
        if (String($select.val() || '') === String(id)) return;
        if (!$select.find('option[value="' + id + '"]').length) {
            $select.append(new Option(text, id, false, false));
        }
        $select.val(String(id)).trigger('change');
    }

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        $(document).on('change', BARCODE_SEL, function () {
            var barcodeId = this.value;
            var $product = $(this).closest('tr').find(PRODUCT_SEL).first();
            if (!barcodeId || !$product.length) return;
            $.get('/api/barcode-info/', {barcode_id: barcodeId}).done(function (data) {
                if (data && data.product_id) setSelect($product, data.product_id, data.product_name);
            });
        });

        $(document).on('change', PRODUCT_SEL, function () {
            var productId = this.value;
            var $barcode = $(this).closest('tr').find(BARCODE_SEL).first();
            if (!productId || !$barcode.length) return;
            $.get('/api/product-barcodes/', {product_id: productId}).done(function (data) {
                var items = (data && data.items) || [];
                var current = String($barcode.val() || '');
                if (items.some(function (b) { return String(b.id) === current; })) return;
                if (!items.length) {
                    if (current) $barcode.val(null).trigger('change');  // บาร์เดิมเป็นของสินค้าอื่น
                    return;
                }
                var primary = items[0];  // บาร์หลัก = บาร์โค้ดแรกที่เพิ่มไว้ให้สินค้านี้
                setSelect($barcode, primary.id, primary.code + (primary.unit_name ? ' (' + primary.unit_name + ')' : ''));
            });
        });
    });

}());
