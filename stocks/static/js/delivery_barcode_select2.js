(function () {
    'use strict';

    var soId = (window.location.pathname.match(/\/(\d+)\/change\//) || [])[1];

    // ดึง CSRF token
    function getCsrf() {
        var m = document.cookie.match(/csrftoken=([^;]+)/);
        if (m) return m[1];
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    // แสดง remaining hint ใต้ barcode input
    function showHint($input, text, color) {
        var $hint = $input.siblings('.barcode-hint');
        if (!$hint.length) {
            $hint = window.django.jQuery('<div class="barcode-hint" style="font-size:11px;margin-top:2px;font-weight:bold;"></div>');
            $input.after($hint);
        }
        $hint.text(text).css('color', color).show();
    }

    // ทำ barcode input เป็น readonly หลัง save
    function lockBarcodeInput($input) {
        $input.prop('readonly', true).css({
            background: '#f3f4f6',
            color: '#374151',
            'border-color': '#d1d5db',
        });
    }

    // ตรวจสอบ barcode (validate + แสดง remaining) ไม่บันทึก
    function checkBarcode($input, callback) {
        var code = ($input.val() || '').trim();
        if (!code || !soId) {
            $input.css('border-color', '');
            return;
        }
        fetch('/api/barcode-remaining/?so_id=' + encodeURIComponent(soId) + '&barcode=' + encodeURIComponent(code))
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.valid) {
                    $input.css('border-color', '#22c55e');
                    var rem = data.remaining;
                    showHint($input,
                        rem > 0 ? ('คงเหลือ: ' + rem + ' ชิ้น') : 'ส่งครบแล้ว (0)',
                        rem > 0 ? '#16a34a' : '#dc2626'
                    );
                    if (callback) callback(true);
                } else {
                    $input.css('border-color', '#dc2626');
                    showHint($input, data.error || 'ไม่พบบาร์โค้ด', '#dc2626');
                    if (callback) callback(false);
                }
            })
            .catch(function () { if (callback) callback(false); });
    }

    // Auto-save row ผ่าน AJAX — เหมือนกด Save
    function autoSaveRow($row) {
        // ป้องกัน save ซ้ำซ้อนในเวลาเดียวกัน
        if ($row.data('saving')) return;

        var $barcodeInput = $row.find('.barcode-code-input');
        var barcodeCode = ($barcodeInput.val() || '').trim();
        if (!barcodeCode || !soId) return;

        var $qtyInput = $row.find('input[name*="delivery_logs-"][name$="-quantity_shipped"]');
        var qty = ($qtyInput.val() || '').trim();
        if (!qty) return;

        var $idInput = $row.find('input[name$="-id"]');
        var logId = $idInput.val() || null;

        var shippingNo  = ($row.find('input[name*="delivery_logs-"][name$="-shipping_no"]').val() || '').trim();
        var notes       = ($row.find('input[name*="delivery_logs-"][name$="-notes"]').val() || '').trim();
        var shippedDate = ($row.find('input[name*="delivery_logs-"][name$="-shipped_date"]').val() || '').trim();

        $row.data('saving', true);
        fetch('/api/delivery-log/save/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrf(),
            },
            body: JSON.stringify({
                so_id: soId,
                log_id: logId,
                barcode_code: barcodeCode,
                shipping_no: shippingNo,
                quantity_shipped: qty,
                notes: notes,
                shipped_date: shippedDate,
            }),
        })
        .then(function (r) { return r.json(); })
        .then(function (result) {
            $row.data('saving', false);
            if (result.success) {
                // อัปเดต id hidden field → กด Save ใหญ่จะ UPDATE ไม่ใช่ CREATE ซ้ำ
                if (!$idInput.val()) {
                    $idInput.val(result.log_id);
                }
                // ล็อค barcode
                lockBarcodeInput($barcodeInput);
                // อัปเดต remaining
                var rem = result.remaining;
                showHint($barcodeInput,
                    '✓ บันทึกแล้ว' + (rem > 0 ? ' — คงเหลือ: ' + rem + ' ชิ้น' : ' — ส่งครบแล้ว'),
                    rem > 0 ? '#16a34a' : '#2563eb'
                );
            } else if (result.errors) {
                if (result.errors.barcode_code) {
                    $barcodeInput.css('border-color', '#dc2626');
                    showHint($barcodeInput, result.errors.barcode_code, '#dc2626');
                }
            } else if (result.error) {
                showHint($barcodeInput, result.error, '#dc2626');
            }
        })
        .catch(function (err) {
            $row.data('saving', false);
            console.error('Autosave error:', err);
        });
    }

    function setupRow(row) {
        if (!row || !window.django) return;
        var $ = django.jQuery;
        var $row = $(row);

        // ป้องกัน setup ซ้ำบน row เดียวกัน
        if ($row.data('barcode-setup')) return;

        var $barcodeInput = $row.find('.barcode-code-input:not([readonly])');
        if (!$barcodeInput.length) return;

        $row.data('barcode-setup', true);

        var barcodeTimer = null;

        // ออกจากกล่อง barcode → validate + ลอง save (ถ้ามี qty แล้ว)
        $barcodeInput.on('blur', function () {
            clearTimeout(barcodeTimer);
            checkBarcode($barcodeInput, function (valid) {
                if (valid) autoSaveRow($row);
            });
        });

        // พิมพ์ใน barcode → validate หลัง 600ms
        $barcodeInput.on('input', function () {
            clearTimeout(barcodeTimer);
            barcodeTimer = setTimeout(function () {
                checkBarcode($barcodeInput, null);
            }, 600);
        });

        // ออกจากกล่อง quantity → auto-save
        $row.find('input[name*="delivery_logs-"][name$="-quantity_shipped"]').on('blur', function () {
            autoSaveRow($row);
        });

        // ออกจากกล่องอื่นๆ (shipping_no, notes) → auto-save ถ้า barcode+qty ครบ
        $row.find(
            'input[name*="delivery_logs-"][name$="-shipping_no"],' +
            'input[name*="delivery_logs-"][name$="-notes"]'
        ).on('blur', function () {
            autoSaveRow($row);
        });
    }

    function initAllRows() {
        document.querySelectorAll('tr').forEach(function (row) {
            if (row.querySelector('.barcode-code-input:not([readonly])')) {
                setupRow(row);
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        setTimeout(initAllRows, 300);

        if (window.django && django.jQuery) {
            django.jQuery(document).on('formset:added', function (e, $row) {
                setTimeout(function () { setupRow($row[0]); }, 100);
            });
        }
    });

}());
