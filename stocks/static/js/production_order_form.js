(function () {
    'use strict';

    // O2 ใบสั่งผลิต: สินค้า <-> บาร์โค้ด <-> สูตรที่ใช้ผลิต <-> ส่วนประกอบ (เลือกทางไหนก่อนก็ได้)
    // - เลือกสินค้า  -> บาร์โค้ดเลือกให้ (บาร์หลักถ้ามีสูตร ไม่งั้นบาร์ล่าสุดที่มีสูตร) + สูตรของบาร์นั้น
    // - เลือก/พิมพ์บาร์โค้ด -> สินค้าของบาร์นั้น + สูตรของบาร์นั้น
    // - ช่องสูตร เห็นเฉพาะสูตรของสินค้าที่เลือก (กรองด้วย id สินค้า)
    // - ส่วนประกอบตามสูตร x จำนวนที่วางแผน แสดงทันที (รายการวัตถุดิบจริงสร้าง/เปลี่ยนตอนกดบันทึก)
    // - บาร์โค้ดที่ไม่มีสูตรของตัวเอง -> เตือน + ปุ่มสร้างสูตร (เปิดหน้า O1 แท็บใหม่ กรอกสินค้า/ชื่อสูตรให้)
    // ตรรกะเลือกอยู่ที่ ProductionOrderAdmin.production_info_view

    function esc(text) {
        return String(text == null ? '' : text).replace(/[&<>"']/g, function (c) {
            return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        var $product = $('#id_product');
        var $barcode = $('#id_barcode_obj');
        var $bom = $('#id_bom');
        var $qty = $('#id_quantity_planned');
        if (!$product.length || !$barcode.length || !$bom.length) return;

        var url = location.pathname.replace(/productionorder\/.*$/, 'productionorder/production-info/');
        var isAdd = /\/add\/?$/.test(location.pathname);
        var savedBomId = String($bom.val() || '');   // สูตรที่บันทึกไว้แล้ว (หน้าแก้ไข)
        var busy = false;                            // กำลังตั้งค่าช่องเอง -> ไม่ยิง request ซ้อน
        var seq = 0;                                 // ตอบกลับช้ากว่า request ใหม่ = ทิ้ง

        // ---- ช่องบาร์โค้ด (autocomplete): เลือกสินค้าแล้ว ค้นได้เฉพาะบาร์ของสินค้านั้น ----
        $.ajaxPrefilter(function (options) {
            if (!options.url || options.url.indexOf('/admin/autocomplete/') === -1) return;
            var productId = $product.val();
            if (!productId) return;
            var isBarcode = function (str) { return /(^|[?&])field_name=barcode_obj(&|$)/.test(str || ''); };
            if (options.data && typeof options.data === 'object') {
                if (options.data.field_name !== 'barcode_obj') return;
                options.data.product_id = productId;
            } else if (typeof options.data === 'string' && isBarcode(options.data)) {
                options.data += '&product_id=' + encodeURIComponent(productId);
            } else if (isBarcode(options.url.split('?')[1])) {
                options.url += '&product_id=' + encodeURIComponent(productId);
            }
        });

        // ---- กล่องเตือน + ส่วนประกอบ ใต้ช่องสูตร ----
        function fieldRow($el) {
            var id = $el.attr('id');
            var $p = $el.parent();
            for (var i = 0; i < 6 && $p.length; i++) {
                if ($p.find('label[for="' + id + '"]').length) return $p;
                $p = $p.parent();
            }
            return $el.parent();
        }
        var $panel = $('<div id="production-bom-panel" style="margin:8px 0 16px;"></div>');
        fieldRow($bom).after($panel);

        function setSelect($select, id, text) {
            if (String($select.val() || '') === String(id)) return;
            if (!$select.find('option[value="' + id + '"]').length) {
                $select.append(new Option(text, id, false, false));
            }
            $select.val(String(id)).trigger('change');
        }

        function clearSelect($select) {
            if (!$select.val()) return;
            $select.val(null).trigger('change');
        }

        function fillBoms(boms, bomId) {
            var current = String($bom.val() || '');
            $bom.empty().append(new Option('---------', ''));
            boms.forEach(function (b) { $bom.append(new Option(b.text, b.id)); });
            $bom.val(bomId ? String(bomId) : '');
            if (String($bom.val() || '') !== current) $bom.trigger('change');
        }

        function render(data) {
            var html = '';
            if (data.error) {
                html += '<div style="padding:8px 12px;border-radius:6px;background:#fee2e2;color:#991b1b;">⚠️ ' + esc(data.error) + '</div>';
            }
            if (data.missing_bom) {
                html += '<div style="padding:8px 12px;border-radius:6px;background:#fef3c7;color:#92400e;margin-bottom:8px;' +
                    'display:flex;flex-wrap:wrap;align-items:center;gap:8px;">' +
                    '<span>⚠️ บาร์โค้ด <b>' + esc(data.missing_bom.code) + '</b> ไม่มีสูตรการผลิต' +
                    (data.bom_id ? ' (ตอนนี้ใช้สูตรรวมของสินค้านี้แทน)' : ' — ยังสั่งผลิตตามสูตรไม่ได้') + '</span>' +
                    '<a href="' + esc(data.missing_bom.create_url) + '" target="_blank" rel="noopener" ' +
                    'style="background:#2563eb;color:#fff;padding:4px 12px;border-radius:4px;text-decoration:none;font-weight:600;">' +
                    '+ สร้างสูตรการผลิต</a>' +
                    '<span style="font-size:12px;">(เปิดแท็บใหม่ สร้างเสร็จแล้วกลับมาหน้านี้ ระบบดึงสูตรให้เอง)</span></div>';
            }
            var bomChanged = String($bom.val() || '') !== savedBomId;
            if (data.ingredients && data.ingredients.length && (isAdd || bomChanged)) {
                html += '<div style="font-weight:600;margin:4px 0;">ส่วนประกอบตามสูตร' +
                    (isAdd ? '' : ' (สูตรใหม่ — จะแทนที่รายการวัตถุดิบเดิมเมื่อกดบันทึก)') + '</div>' +
                    '<table style="border-collapse:collapse;width:100%;max-width:760px;font-size:13px;">' +
                    '<thead><tr>' +
                    '<th style="text-align:left;padding:4px 8px;border-bottom:1px solid #9ca3af;">วัตถุดิบ</th>' +
                    '<th style="text-align:left;padding:4px 8px;border-bottom:1px solid #9ca3af;">บาร์โค้ด</th>' +
                    '<th style="text-align:right;padding:4px 8px;border-bottom:1px solid #9ca3af;">ต่อ 1 หน่วย</th>' +
                    '<th style="text-align:right;padding:4px 8px;border-bottom:1px solid #9ca3af;">ต้องใช้ทั้งหมด</th>' +
                    '<th style="text-align:left;padding:4px 8px;border-bottom:1px solid #9ca3af;">หน่วย</th>' +
                    '</tr></thead><tbody>';
                data.ingredients.forEach(function (it) {
                    html += '<tr>' +
                        '<td style="padding:4px 8px;border-bottom:1px solid rgba(156,163,175,.35);">' + esc(it.name) +
                        (it.is_scrap ? ' <span style="font-size:11px;color:#b45309;">(ของเสีย)</span>' : '') + '</td>' +
                        '<td style="padding:4px 8px;border-bottom:1px solid rgba(156,163,175,.35);">' + esc(it.barcode || '-') + '</td>' +
                        '<td style="padding:4px 8px;text-align:right;border-bottom:1px solid rgba(156,163,175,.35);">' + esc(it.per_unit) + '</td>' +
                        '<td style="padding:4px 8px;text-align:right;font-weight:600;border-bottom:1px solid rgba(156,163,175,.35);">' + esc(it.total) + '</td>' +
                        '<td style="padding:4px 8px;border-bottom:1px solid rgba(156,163,175,.35);">' + esc(it.unit) + '</td>' +
                        '</tr>';
                });
                html += '</tbody></table>';
            } else if ($bom.val() === '' && $product.val() && !data.error && (isAdd || bomChanged)) {
                html += '<div style="color:#b45309;">ยังไม่มีสูตรการผลิตสำหรับสินค้านี้</div>';
            }
            $panel.html(html);
        }

        function refresh(trigger) {
            if (!$product.val() && !$barcode.val()) {
                fillBoms([], null);
                $panel.empty();
                return;
            }
            var mine = ++seq;
            $.get(url, {
                trigger: trigger,
                product_id: $product.val() || '',
                barcode_id: $barcode.val() || '',
                bom_id: $bom.val() || '',
                qty: $qty.val() || ''
            }).done(function (data) {
                if (mine !== seq || !data) return;
                if (data.error) {
                    // สินค้าที่ไม่มี BOM (เช่นเลือกจากบาร์โค้ด) -> ไม่ตั้งค่าให้ แค่เตือน
                    render(data);
                    return;
                }
                busy = true;
                try {
                    if (data.product) setSelect($product, data.product.id, data.product.text);
                    if (trigger === 'product' || trigger === 'barcode') {
                        if (data.barcode) setSelect($barcode, data.barcode.id, data.barcode.text);
                        else clearSelect($barcode);
                    }
                    fillBoms(data.boms || [], data.bom_id);
                    $('#pd-machine-display').text(data.machine || '-');
                } finally {
                    busy = false;
                }
                render(data);
            });
        }

        $(document).on('change', '#id_product', function () {
            if (busy) return;
            if (!$product.val()) {
                // ล้างสินค้า -> ล้างบาร์โค้ด/สูตรที่เป็นของสินค้าเดิมด้วย
                busy = true;
                try { clearSelect($barcode); fillBoms([], null); } finally { busy = false; }
                $('#pd-machine-display').text('-');
                $panel.empty();
                return;
            }
            refresh('product');
        });
        $(document).on('change', '#id_barcode_obj', function () {
            if (busy) return;
            refresh('barcode');
        });
        $(document).on('change', '#id_bom', function () {
            if (busy) return;
            refresh('bom');
        });
        var qtyTimer = null;
        $qty.on('input change', function () {
            clearTimeout(qtyTimer);
            qtyTimer = setTimeout(function () { refresh('qty'); }, 300);
        });

        // กลับมาจากแท็บสร้างสูตร -> ดึงสูตรใหม่ (ถ้าบาร์ที่เลือกเพิ่งมีสูตร ให้เลือกสูตรนั้นเลย)
        var waitingBom = false;
        $panel.on('click', 'a[target="_blank"]', function () { waitingBom = true; });
        window.addEventListener('focus', function () {
            if (!waitingBom) return;
            waitingBom = false;
            refresh($barcode.val() ? 'barcode' : 'product');
        });

        // เปิดหน้า: ตั้งตัวเลือกสูตรตามสินค้าที่มีอยู่ (หน้าแก้ไข/ฟอร์มที่ error กลับมา) ไม่เปลี่ยนค่าที่เลือกไว้
        if ($product.val() || $barcode.val()) refresh('init');
    });

}());
