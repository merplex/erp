(function () {
    'use strict';

    // W5 สินค้าในแท็ก: เลือกบาร์โค้ด -> ขึ้นชื่อสินค้าทันที (AJAX) + เตือนถ้าสินค้าซ้ำกับแถวอื่น
    // (บาร์โค้ดต่างกันแต่เป็นสินค้าเดียวกัน) — server เช็คซ้ำอีกชั้นตอนบันทึก
    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;
        var SELECT = 'select[name^="Product_tags-"][name$="-barcode"]';

        function rowOf(el) { return $(el).closest('tbody.form-group'); }

        function isDeleted($row) {
            var del = $row.find('input[name$="-DELETE"]');
            return del.length && del.prop('checked');
        }

        function checkDuplicates() {
            var seen = {};
            $('tbody.form-group:not(.empty-form) .tag-product').each(function () {
                var $row = rowOf(this);
                $row.find('.tag-dup-warning').remove();
                var id = $(this).attr('data-product-id');
                if (!id || isDeleted($row)) return;
                if (seen[id]) {
                    var msg = $('<div class="tag-dup-warning"></div>')
                        .text('⚠️ สินค้าซ้ำกับแถวที่ ' + seen[id].no + ' (' + seen[id].name + ')');
                    var $cell = $row.find('td.field-barcode');
                    ($cell.length ? $cell : $row.find('td').last()).append(msg);
                } else {
                    seen[id] = {no: $row.find('td.field-row_no').length ? rowNumber($row) : '', name: $(this).text()};
                }
            });
        }

        function rowNumber($row) {
            return $('tbody.form-group:not(.empty-form)').filter(':visible').index($row) + 1;
        }

        $(document).on('change', SELECT, function () {
            var $row = rowOf(this);
            var $product = $row.find('.tag-product');
            $product.text('').removeAttr('data-product-id');
            if (!this.value) { checkDuplicates(); return; }
            $product.css('opacity', 0.5);
            $.get('/api/barcode-info/', {barcode_id: this.value})
                .done(function (data) {
                    if (!data || !data.product_id) return;
                    $product.text(data.product_name).attr('data-product-id', data.product_id);
                })
                .always(function () {
                    $product.css('opacity', '');
                    checkDuplicates();
                });
        });
        $(document).on('change', 'input[name^="Product_tags-"][name$="-DELETE"]', checkDuplicates);
    });
}());
