(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        // ---- หน้า detail ของ CustomerProductContract (ไม่ใช่ inline) ----
        // เมื่อผู้ใช้เปลี่ยน barcode → AJAX update product info แบบ smooth (ไม่ reload)

        var $barcodeMain = $('select[name="barcode"]');
        if ($barcodeMain.length) {
            var initialVal = $barcodeMain.val();

            // ดึง CSRF token
            function getCsrf() {
                var m = document.cookie.match(/csrftoken=([^;]+)/);
                if (m) return m[1];
                var el = document.querySelector('[name=csrfmiddlewaretoken]');
                return el ? el.value : '';
            }

            // fade element แล้ว update text/html แล้ว fade กลับ
            function fadeUpdate($el, newContent, isHtml) {
                $el.css({ transition: 'opacity 0.2s', opacity: 0 });
                setTimeout(function () {
                    if (isHtml) $el.html(newContent);
                    else $el.text(newContent);
                    $el.css('opacity', 1);
                }, 220);
            }

            $barcodeMain.on('change', function () {
                var newVal = this.value;
                if (!newVal) return;
                if (newVal === initialVal) return;
                initialVal = newVal;

                // ดึง contract id จาก URL
                var contractId = (window.location.pathname.match(/\/(\d+)\/change\//) || [])[1] || null;

                fetch('/api/contract/update-barcode/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrf(),
                    },
                    body: JSON.stringify({
                        contract_id: contractId,
                        barcode_id: newVal,
                    }),
                })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.error) return;

                    // อัปเดต field "สินค้า" (readonly .field-product .readonly)
                    var $productField = $('.field-product .readonly');
                    if ($productField.length) {
                        fadeUpdate($productField, data.product_name || '-', false);
                    }

                    // อัปเดต field "ข้อมูลหน่วย" (readonly .field-barcode_unit_detail .readonly)
                    var $unitField = $('.field-barcode_unit_detail .readonly');
                    if ($unitField.length) {
                        var factor = data.conversion_factor || 1;
                        var unit = data.unit_name || 'ชิ้น';
                        var html = '<span style="color:#374151;">หน่วย: <b>' + unit + '</b> &nbsp;|&nbsp; ' + factor + ' ชิ้น/หน่วย</span>';
                        fadeUpdate($unitField, html, true);
                    }
                })
                .catch(function (err) {
                    console.error('contract update-barcode error:', err);
                });
            });
        }

        // ---- inline ใน Customer page ----
        // เมื่อเลือก barcode ใน row → แสดง hint ให้ผู้ใช้กด Save
        $(document).on('change', 'select[name$="-barcode"]', function () {
            var val = this.value;
            if (!val) return;

            var $td = $(this).closest('td');
            if (!$td.find('.barcode-save-hint').length) {
                $td.append(
                    '<div class="barcode-save-hint" style="font-size:11px;color:#2563eb;margin-top:3px;">กด Save เพื่อแสดงชื่อสินค้า</div>'
                );
            }
        });
    });

}());
