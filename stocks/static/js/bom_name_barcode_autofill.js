(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        // ---- ฟอร์ม BOM หลัก: เลือกสินค้าแล้วเติม "ชื่อสูตร" เป็นรหัสบาร์โค้ดของสินค้านั้นให้อัตโนมัติ ----
        // ระบบใช้ BOM.name == รหัสบาร์โค้ด เป็นตัวจับคู่สูตรตอนขาย (ดู product_bom_by_barcode_api)
        // จึงควรให้ค่านี้ตรงกับบาร์โค้ดจริงเสมอ แทนที่จะให้พิมพ์เองอิสระ
        var $nameInput = $('#id_name');
        if (!$nameInput.length) return;

        var $chooser = $(
            '<select id="id_name_barcode_chooser" style="margin-top:6px; max-width: 400px;">' +
            '<option value="">— เลือกบาร์โค้ดอื่นของสินค้านี้ —</option>' +
            '</select>'
        );
        $chooser.hide().insertAfter($nameInput);

        $chooser.on('change', function () {
            var code = $(this).find('option:selected').attr('data-code');
            if (code) $nameInput.val(code);
        });

        function loadBarcodesForProduct(productId) {
            $chooser.hide().empty().append('<option value="">— เลือกบาร์โค้ดอื่นของสินค้านี้ —</option>');
            if (!productId) return;

            $.get('/api/product-barcodes/', {product_id: productId}).done(function (data) {
                var items = (data && data.items) || [];
                if (!items.length) return;

                // บาร์หลัก = บาร์โค้ดแรกที่เพิ่มไว้ให้สินค้านี้ (เรียงตาม id เหมือน logic เดิมของ BOMIngredient)
                var primary = items[0];
                $nameInput.val(primary.code);

                if (items.length > 1) {
                    items.forEach(function (item) {
                        var label = item.code + (item.unit_name ? ' (' + item.unit_name + ')' : '');
                        $chooser.append(
                            $('<option></option>').val(item.id).text(label).attr('data-code', item.code)
                        );
                    });
                    $chooser.val(primary.id).show();
                }
            });
        }

        $(document).on('change', '#id_product', function () {
            loadBarcodesForProduct(this.value);
        });
    });

}());
