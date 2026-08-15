(function () {
    'use strict';

    // ⚠️ ไฟล์นี้เคยมี logic auto-save + สร้างแถวใหม่แบบ dynamic (พิมพ์บาร์โค้ด + "Add another")
    // ทั้งหมดถูกตัดออกแล้ว เพราะเป็นต้นตอบั๊กบันทึกซ้ำที่แก้ไม่หายสักที — Django formset ปฏิบัติกับ
    // แถวที่เพิ่มมาแบบ dynamic เป็น "extra form" เสมอ ไม่สนใจค่า -id ที่ส่งมาเลย ต่อให้ auto-save
    // ผูก id ถูกต้องแค่ไหนก็ตาม พอกด Save ทั้งหน้า Django ก็ยังสร้างแถวใหม่ซ้ำอยู่ดี
    //
    // ตอนนี้สร้างรายการส่งของใหม่ผ่าน "checklist ส่งของ" ที่หัวเอกสารแทน (ดู
    // stocks/templates/admin/sales_shipment_panel.html + SalesOrderAdmin.ship_batch_view ใน
    // admin.py) ซึ่งเป็นฟอร์มธรรมดา submit ตรงไป view แยกต่างหาก ไม่ผ่าน formset เลย
    //
    // ไฟล์นี้เหลือหน้าที่เดียว: แสดงแถบสรุปสถานะ "ค้างส่ง" (แดง) / "ส่งเกิน" (เขียว) เหนือ checklist

    var soId = (window.location.pathname.match(/\/(\d+)\/change\//) || [])[1];

    function injectBarStyles() {
        if (document.getElementById('delivery-status-bar-style')) return;
        var style = document.createElement('style');
        style.id = 'delivery-status-bar-style';
        style.textContent = [
            '@keyframes delivery-status-scroll {',
            '  0%   { transform: translateX(0); }',
            '  100% { transform: translateX(-100%); }',
            '}',
            '.delivery-status-bar {',
            '  display: flex; align-items: center; gap: 8px;',
            '  margin: 0 0 8px 0; font-size: 12px; overflow: hidden;',
            '}',
            '.delivery-status-bar .dsb-label { white-space: nowrap; font-weight: bold; flex-shrink: 0; }',
            '.delivery-status-bar .dsb-track { overflow: hidden; flex: 1; }',
            '.delivery-status-bar .dsb-content { display: inline-block; white-space: nowrap; }',
            '.delivery-status-bar .dsb-content.scrolling { animation: delivery-status-scroll 30s linear infinite; }',
        ].join('\n');
        document.head.appendChild(style);
    }

    function renderBar(container, id, label, color, items, formatItem) {
        var $ = window.django && django.jQuery;
        if (!$) return;
        var $container = $(container);
        var $existing = $container.find('#' + id);
        if (!items || !items.length) {
            $existing.hide();
            return;
        }
        var text = items.map(formatItem).join('     ·     ');
        if ($existing.length) {
            $existing.find('.dsb-content').text(text).css('color', color);
            $existing.show();
        } else {
            injectBarStyles();
            var $bar = $(
                '<div id="' + id + '" class="delivery-status-bar">' +
                '  <span class="dsb-label" style="color:' + color + ';">' + label + '</span>' +
                '  <div class="dsb-track"><span class="dsb-content" style="color:' + color + ';"></span></div>' +
                '</div>'
            );
            $bar.find('.dsb-content').text(text);
            $container.append($bar);
        }
        // ตรวจว่าต้อง scroll ไหม (เนื้อหายาวเกินพื้นที่)
        setTimeout(function () {
            var $c = $container.find('#' + id + ' .dsb-content');
            var $t = $container.find('#' + id + ' .dsb-track');
            if (!$c.length || !$t.length) return;
            if ($c[0].scrollWidth > $t[0].offsetWidth) {
                $c.addClass('scrolling').css('animation-duration', Math.max(15, items.length * 5) + 's');
            } else {
                $c.removeClass('scrolling').css('animation-duration', '');
            }
        }, 50);
    }

    function loadStatusBars() {
        if (!soId) return;
        var container = document.getElementById('delivery-status-bars');
        if (!container) return;
        fetch('/api/pending-barcodes/?so_id=' + encodeURIComponent(soId))
            .then(function (r) { return r.json(); })
            .then(function (data) {
                renderBar(container, 'delivery-pending-bar', '📋 ค้างส่ง:', '#dc2626', data.items, function (i) {
                    return i.barcode + '  (ค้าง ' + i.remaining + ' ' + (i.unit_name || 'ชิ้น') + ')';
                });
                renderBar(container, 'delivery-over-bar', '📈 ส่งเกิน:', '#16a34a', data.over_items, function (i) {
                    return i.barcode + '  (เกิน ' + i.over + ' ' + (i.unit_name || 'ชิ้น') + ')';
                });
            })
            .catch(function () {});
    }

    document.addEventListener('DOMContentLoaded', function () {
        // panel ถูกย้ายเข้าตำแหน่งจริงด้วย JS ของ admin.py (move_panel_script) ซึ่งทำงานหลัง
        // DOMContentLoaded เล็กน้อย — รอสักครู่ก่อนค่อยโหลดแถบสถานะ ให้ #delivery-status-bars
        // มีอยู่จริงในหน้าก่อน
        setTimeout(loadStatusBars, 400);
    });

}());
