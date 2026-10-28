(function () {
    'use strict';

    // W5 สินค้าในแท็ก — แถวเพิ่มสินค้า: บาร์โค้ด <-> สินค้า เติมกันเองด้วย product_barcode_sync.js (ตัวเดียวกับใบ SO)
    // เลือกสินค้าแล้ว -> ขึ้นบริษัท/ราคา (AJAX) + เตือนถ้าสินค้าซ้ำกับแถวอื่นหรือมีแท็กนี้อยู่แล้ว
    // (บาร์โค้ดต่างกันแต่เป็นสินค้าเดียวกันก็จับได้) — server เช็คซ้ำอีกชั้นตอนบันทึก
    // + ตารางสินค้าเดิม: ช่องค้นหา (กรองฝั่ง browser) และขีดฆ่าแถวที่ติ๊กเอาออก
    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;
        var PRODUCT = 'select[name^="Product_tags-"][name$="-product"]';

        function rowOf(el) { return $(el).closest('tbody.form-group'); }

        function isDeleted($row) {
            var del = $row.find('input[name$="-DELETE"]');
            return del.length && del.prop('checked');
        }

        function rowNumber($row) {
            return $('tbody.form-group:not(.empty-form)').filter(':visible').index($row) + 1;
        }

        function checkDuplicates() {
            var existing = {};
            $('tr.tag-existing').each(function () {
                if (!$(this).find('input[name="remove_tag_product"]').prop('checked')) {
                    existing[$(this).attr('data-product-id')] = true;
                }
            });
            var seen = {};
            $('tbody.form-group:not(.empty-form) ' + PRODUCT).each(function () {
                var $row = rowOf(this);
                $row.find('.tag-dup-warning').remove();
                var id = this.value;
                if (!id || isDeleted($row)) return;
                var name = $(this).find('option:selected').text();
                var text = existing[id] ? '⚠️ ' + name + ' มีแท็กนี้อยู่แล้ว'
                    : seen[id] ? '⚠️ สินค้าซ้ำกับแถวที่ ' + seen[id].no + ' (' + seen[id].name + ')' : '';
                if (text) {
                    $row.find('td.field-product').append($('<div class="tag-dup-warning"></div>').text(text));
                } else {
                    seen[id] = {no: rowNumber($row), name: name};
                }
            });
        }

        function fillSuppliers($row, productId) {
            var $sup = $row.find('.tag-suppliers').empty();
            var $price = $row.find('.tag-prices').empty();
            if (!productId) return;
            $.get('/api/product-suppliers/', {product_id: productId}).done(function (data) {
                var items = (data && data.items) || [];
                if (!items.length) { $sup.text('—'); $price.text('—'); return; }
                items.forEach(function (it) {
                    $sup.append($('<div></div>').attr('title', it.name).text(it.short));
                    $price.append($('<div></div>').text(it.price));
                });
            });
        }

        $(document).on('change', PRODUCT, function () {
            fillSuppliers(rowOf(this), this.value);
            checkDuplicates();
        });
        $(document).on('change', 'input[name^="Product_tags-"][name$="-DELETE"]', checkDuplicates);
        $(document).on('change', 'input[name="remove_tag_product"]', function () {
            $(this).closest('tr').toggleClass('tag-removing', this.checked);
            checkDuplicates();
        });

        // หน้าโหลดกลับมาพร้อม error (มีสินค้าเลือกค้างไว้) -> เติมบริษัท/ราคาให้
        $('tbody.form-group:not(.empty-form) ' + PRODUCT).each(function () {
            if (this.value) fillSuppliers(rowOf(this), this.value);
        });

        var timer;
        $(document).on('input', '.tag-existing-search', function () {
            var q = this.value.trim().toLowerCase();
            clearTimeout(timer);
            timer = setTimeout(function () {
                $('tr.tag-existing').each(function () {
                    // ค้นชื่อบริษัทเต็มได้ด้วย (ในตารางแสดงชื่อสั้น ชื่อเต็มอยู่ใน title)
                    var text = this.textContent + ' ' + $(this).find('[title]').map(function () { return this.title; }).get().join(' ');
                    this.style.display = !q || text.toLowerCase().indexOf(q) !== -1 ? '' : 'none';
                });
            }, 150);
        });
        // Enter ในช่องค้นหาอย่าไป submit ฟอร์ม
        $(document).on('keydown', '.tag-existing-search', function (e) { if (e.key === 'Enter') e.preventDefault(); });
    });
}());
