(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        var $supplierField = $('#id_supplier');
        if (!$supplierField.length) return; // ไม่ใช่หน้า PurchaseOrder add/change

        // ---- PurchaseItemInline: เลือกสินค้าเสร็จ → โชว์ราคาซื้อจาก supplier รายนี้ทันที ----
        // ตาม logic เดียวกับ PurchaseItem.save() (ราคาจาก ProductSupplier ถ้ามี ไม่งั้นราคาทุนมาตรฐาน)
        // เติมให้เฉพาะตอนช่อง unit_price ยังว่าง/เป็น 0 (ไม่ทับราคาที่พิมพ์เอง)
        $(document).on('change', 'select[name$="-product"]', function () {
            var productId = this.value;
            if (!productId) return;

            var $row = $(this).closest('tr');
            var $priceInput = $row.find('input[name$="-unit_price"]');
            if (!$priceInput.length) return;
            var current = parseFloat($priceInput.val());
            if (current) return; // มีราคาอยู่แล้ว ไม่ทับ

            $.get('/api/purchase-quotation-price/', {
                supplier_id: $supplierField.val(),
                product_id: productId,
            }).done(function (data) {
                if (!data || data.suggested_price === undefined) return;
                $priceInput.val(data.suggested_price);
            });
        });
    });

}());
