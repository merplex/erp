(function () {
    'use strict';

    // O4 เครื่องจักร: inline "สินค้าที่ผลิตได้" — สินค้า <-> บาร์โค้ด เลือกทางไหนก่อนก็ได้ (แบบเดียวกับ O2 ใบสั่งผลิต)
    // - เลือกสินค้า -> บาร์โค้ดเลือกให้ (บาร์หลักถ้ามีสูตร ไม่งั้นบาร์ล่าสุดที่มีสูตร) เปลี่ยนเองได้
    // - เลือก/พิมพ์บาร์โค้ด -> สินค้าของบาร์นั้น
    // - ช่องบาร์โค้ดของแถวที่เลือกสินค้าแล้ว ค้นได้เฉพาะบาร์ของสินค้านั้น
    // ใช้ตรรกะเดียวกับ O2 ผ่าน /admin/stocks/productionorder/production-info/
    var PREFIX = 'capacities-';
    var PRODUCT_SEL = 'select[name^="' + PREFIX + '"][name$="-product"]';
    var BARCODE_SEL = 'select[name^="' + PREFIX + '"][name$="-barcode_obj"]';

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;
        if (!$(PRODUCT_SEL).length && !$('#' + PREFIX + 'empty').length) return;

        var url = location.pathname.replace(/\/stocks\/machine\/.*$/, '/stocks/productionorder/production-info/');
        var busy = false;
        var openingProductId = '';   // สินค้าของแถวที่กำลังเปิดช่องบาร์โค้ด

        function rowOf(el) { return $(el).closest('tr, .inline-related, .form-row'); }

        function setSelect($select, id, text) {
            if (String($select.val() || '') === String(id)) return;
            if (!$select.find('option[value="' + id + '"]').length) {
                $select.append(new Option(text, id, false, false));
            }
            $select.val(String(id)).trigger('change');
        }

        $(document).on('select2:opening', BARCODE_SEL, function () {
            openingProductId = rowOf(this).find(PRODUCT_SEL).first().val() || '';
        });

        $.ajaxPrefilter(function (options) {
            if (!options.url || options.url.indexOf('/admin/autocomplete/') === -1 || !openingProductId) return;
            var match = function (str) {
                return /(^|[?&])field_name=barcode_obj(&|$)/.test(str || '') &&
                    /(^|[?&])model_name=machineproductcapacity(&|$)/.test(str || '');
            };
            if (options.data && typeof options.data === 'object') {
                if (options.data.field_name !== 'barcode_obj' || options.data.model_name !== 'machineproductcapacity') return;
                options.data.product_id = openingProductId;
            } else if (typeof options.data === 'string' && match(options.data)) {
                options.data += '&product_id=' + encodeURIComponent(openingProductId);
            } else if (match(options.url.split('?')[1])) {
                options.url += '&product_id=' + encodeURIComponent(openingProductId);
            }
        });

        function sync(el, trigger) {
            var $row = rowOf(el);
            var $product = $row.find(PRODUCT_SEL).first();
            var $barcode = $row.find(BARCODE_SEL).first();
            if (!$product.length || !$barcode.length) return;
            if (trigger === 'product' && !$product.val()) {
                busy = true;
                try { if ($barcode.val()) $barcode.val(null).trigger('change'); } finally { busy = false; }
                return;
            }
            if (trigger === 'barcode' && !$barcode.val()) return;  // ล้างบาร์ = ใช้กับทุกบาร์ของสินค้า
            $.get(url, {
                trigger: trigger,
                product_id: $product.val() || '',
                barcode_id: $barcode.val() || ''
            }).done(function (data) {
                if (!data || data.error) return;
                busy = true;
                try {
                    if (data.product) setSelect($product, data.product.id, data.product.text);
                    if (trigger === 'product') {
                        if (data.barcode) setSelect($barcode, data.barcode.id, data.barcode.text);
                        else if ($barcode.val()) $barcode.val(null).trigger('change');
                    }
                } finally {
                    busy = false;
                }
            });
        }

        $(document).on('change', PRODUCT_SEL, function () {
            if (!busy) sync(this, 'product');
        });
        $(document).on('change', BARCODE_SEL, function () {
            if (!busy) sync(this, 'barcode');
        });
    });

}());
