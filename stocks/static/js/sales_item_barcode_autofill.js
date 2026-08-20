(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        var $customerField = $('#id_customer');

        // ---- SalesItemInline: เลือกสินค้า/บาร์โค้ดเสร็จ → โชว์ราคาขายทันที ไม่ต้องรอ save ----
        // ราคา: ราคาสัญญาลูกค้ารายนี้ (ถ้ามี) ไม่งั้นราคาขายมาตรฐานของสินค้า คูณ conversion_factor
        // ตาม logic เดียวกับ SalesItem.save() — ไม่ทับราคาที่ผู้ใช้พิมพ์เอง (ดู data('userEdited'))
        // แต่จะทับเสมอเมื่อเปลี่ยนสินค้า เพราะราคาที่ค้างอยู่เป็นของสินค้าตัวก่อนหน้า ไม่ใช่ตัวใหม่
        function fetchAndFillSalePrice($row, productId, factor) {
            if (!productId || !$customerField.length) return;
            var $priceInput = $row.find('input[name$="-sale_price"]');
            if (!$priceInput.length) return;
            if ($priceInput.data('userEdited')) return;

            $.get('/api/sales-quotation-price/', {
                customer_id: $customerField.val(),
                product_id: productId,
            }).done(function (data) {
                if (!data || data.suggested_price === undefined) return;
                var unitPrice = parseFloat(data.suggested_price) || 0;
                $priceInput.data('autofilling', true);
                $priceInput.val((unitPrice * (factor || 1)).toFixed(2));
                $priceInput.data('autofilling', false);
            });
        }

        // ผู้ใช้พิมพ์ราคาเอง → กันไม่ให้ auto-fill ทับ (เว้นแต่เปลี่ยนสินค้าใหม่)
        $(document).on('input', 'input[name$="-sale_price"]', function () {
            var $input = $(this);
            if ($input.data('autofilling')) return;
            $input.data('userEdited', true);
        });

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
                    if (String($productSelect.val()) === String(data.product_id)) {
                        fetchAndFillSalePrice($row, data.product_id, data.conversion_factor);
                        return;
                    }
                    var newOption = new Option(data.product_name, data.product_id, true, true);
                    $productSelect.append(newOption).trigger('change');
                    fetchAndFillSalePrice($row, data.product_id, data.conversion_factor);
                });
        });

        // ---- เลือกสินค้าตรงๆ โดยไม่ผ่านบาร์โค้ด → factor = 1 ตาม logic ฝั่ง server ----
        // เปลี่ยนสินค้า = ราคาเดิม (ของสินค้าตัวก่อนหน้า) ไม่มีความหมายอีกต่อไป เคลียร์ flag เพื่อให้ auto-fill ทำงานใหม่
        $(document).on('change', 'select[name$="-product"]', function () {
            var $row = $(this).closest('tr');
            $row.find('input[name$="-sale_price"]').data('userEdited', false);
            if ($row.find('select[name$="-barcode_obj"]').val()) return; // มี barcode อยู่แล้ว ปล่อยให้ handler ด้านบนจัดการ
            fetchAndFillSalePrice($row, this.value, 1);
        });
    });

}());
