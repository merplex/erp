(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        var $productField = $('#id_product');
        if (!$productField.length) return; // ไม่ใช่หน้า AdvanceOrderRule add/change

        // เดินขึ้นไปหา container ของ field (รองรับได้ทุก theme เพราะหา label ของ field นั้นเป็นตัวอ้างอิง)
        function getFieldRow(id) {
            var $el = $('#' + id);
            if (!$el.length) return $();
            var $p = $el.parent();
            for (var i = 0; i < 6 && $p.length; i++) {
                if ($p.find('label[for="' + id + '"]').length) return $p;
                $p = $p.parent();
            }
            return $el.parent();
        }

        var $supplierRow = getFieldRow('id_supplier');
        var $barcodeRow = getFieldRow('id_barcode_obj');
        var $bomRow = getFieldRow('id_bom');

        function toggleFieldsByType() {
            var type = $('input[name="order_type"]:checked').val();
            if (type === 'PRODUCTION') {
                $supplierRow.hide();
                $barcodeRow.show();
                $bomRow.show();
            } else {
                $supplierRow.show();
                $barcodeRow.hide();
                $bomRow.hide();
            }
        }

        function setSelect2Value($select, id, text) {
            if (!id) return;
            if (String($select.val()) === String(id)) return;
            var newOption = new Option(text, id, true, true);
            $select.append(newOption).trigger('change');
        }

        function loadBarcodesForProduct(productId, autoSelectFirst) {
            var $barcodeSelect = $('#id_barcode_obj');
            if (!productId) {
                $barcodeSelect.empty().trigger('change');
                return;
            }
            $.get('/api/product-barcodes/', {product_id: productId}).done(function (data) {
                var items = (data && data.items) || [];
                $barcodeSelect.empty();
                $barcodeSelect.append(new Option('---------', ''));
                items.forEach(function (b) {
                    $barcodeSelect.append(new Option(b.code + ' (' + b.unit_name + ')', b.id));
                });
                if (autoSelectFirst && items.length) {
                    $barcodeSelect.val(items[0].id);
                }
                $barcodeSelect.trigger('change');
            });
        }

        function fetchAndFillBom(productId, barcodeId) {
            if (!productId) return;
            $.get('/api/product-bom-by-barcode/', {product_id: productId, barcode_id: barcodeId || ''})
                .done(function (data) {
                    if (!data || !data.bom_id) return;
                    setSelect2Value($('#id_bom'), data.bom_id, data.bom_name);
                });
        }

        function fetchAndFillSupplier(productId) {
            var $supplierSelect = $('#id_supplier');
            if ($supplierSelect.val()) return; // มีค่าอยู่แล้ว ไม่ทับ
            $.get('/api/recommended-supplier/', {product_id: productId}).done(function (data) {
                if (!data || !data.supplier_id) return;
                setSelect2Value($supplierSelect, data.supplier_id, data.supplier_name);
            });
        }

        // ---- radio order_type: toggle fields ----
        $(document).on('change', 'input[name="order_type"]', toggleFieldsByType);
        toggleFieldsByType();

        // ---- เลือกสินค้า: โหลดบาร์โค้ดของสินค้านี้ + แนะนำ supplier ----
        $(document).on('change', '#id_product', function () {
            var productId = this.value;
            loadBarcodesForProduct(productId, true);
            if (productId) fetchAndFillSupplier(productId);
        });

        // ---- เลือกบาร์โค้ด: หา BOM ที่ตรงกันมาเติมให้อัตโนมัติ ----
        $(document).on('change', '#id_barcode_obj', function () {
            var productId = $productField.val();
            fetchAndFillBom(productId, this.value);
        });

        // ---- กรณีหน้าเพิ่มใหม่ที่มาพร้อม ?product= (ปุ่ม + จากหน้า C0) ----
        // ให้โหลดบาร์โค้ด+เลือกตัวหลักให้ทันทีตั้งแต่เปิดหน้า (ไม่ต้องรอ change)
        if (!$('#id_barcode_obj option').filter(function () { return this.value; }).length && $productField.val()) {
            loadBarcodesForProduct($productField.val(), true);
        }
    });

}());
