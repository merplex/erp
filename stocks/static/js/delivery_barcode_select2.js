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
            $hint = window.django.jQuery('<div class="barcode-hint" style="font-size:11px;margin-top:2px;font-weight:bold;text-align:center;width:180px;"></div>');
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
                    var unit = data.unit_name || 'ชิ้น';
                    showHint($input,
                        rem > 0 ? ('คงเหลือ: ' + rem + ' ' + unit) : 'ส่งครบแล้ว (0)',
                        rem > 0 ? '#16a34a' : '#dc2626'
                    );
                    if (callback) callback(true);
                } else {
                    $input.css('border-color', '#dc2626');
                    showHint($input, data.error || 'ไม่พบบาร์โค้ดนี้ ในใบสั่งขาย', '#dc2626');
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
                var unit = result.unit_name || 'ชิ้น';
                showHint($barcodeInput,
                    '✓ บันทึกแล้ว' + (rem > 0 ? ' — คงเหลือ: ' + rem + ' ' + unit : ' — ส่งครบแล้ว'),
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

    // --- Pending Bar: แถบ scroll แสดงบาร์โค้ดที่ยังส่งไม่ครบ ---
    function injectPendingBarStyles() {
        if (document.getElementById('pending-bar-style')) return;
        var style = document.createElement('style');
        style.id = 'pending-bar-style';
        style.textContent = [
            '@keyframes pending-scroll {',
            '  0%   { transform: translateX(0); }',
            '  100% { transform: translateX(-100%); }',
            '}',
            '#delivery-pending-bar {',
            '  display: flex;',
            '  align-items: center;',
            '  gap: 8px;',
            '  margin: 6px 0 4px 0;',
            '  font-size: 12px;',
            '  overflow: hidden;',
            '}',
            '#delivery-pending-bar .pb-label {',
            '  white-space: nowrap;',
            '  font-weight: bold;',
            '  color: #dc2626;',
            '  flex-shrink: 0;',
            '}',
            '#delivery-pending-bar .pb-track {',
            '  overflow: hidden;',
            '  flex: 1;',
            '}',
            '#delivery-pending-bar .pb-content {',
            '  display: inline-block;',
            '  white-space: nowrap;',
            '  color: #dc2626;',
            '}',
            '#delivery-pending-bar .pb-content.scrolling {',
            '  animation: pending-scroll 30s linear infinite;',
            '}',
        ].join('\n');
        document.head.appendChild(style);
    }

    function findAddAnotherAnchor($) {
        // หา "Add another Sales delivery log" link/button
        // ลอง selector หลายแบบรองรับ Unfold และ Django vanilla
        var $anchor = null;

        // 1. หา <a> ที่มีข้อความ "Add another" ใน inline delivery_logs
        $('a').each(function () {
            var text = $(this).text().toLowerCase();
            if (text.indexOf('add another') !== -1 || text.indexOf('เพิ่ม') !== -1) {
                var $closest = $(this).closest('[id*="delivery_logs"], [class*="delivery"]');
                if ($closest.length) {
                    $anchor = $(this);
                    return false;
                }
            }
        });

        // 2. fallback: หา <a> "Add another" ตัวสุดท้ายในหน้า
        if (!$anchor || !$anchor.length) {
            $('a').each(function () {
                var text = $(this).text().toLowerCase();
                if (text.indexOf('add another') !== -1) {
                    $anchor = $(this);
                }
            });
        }

        return $anchor;
    }

    function renderPendingBar(items) {
        if (!window.django) return;
        var $ = django.jQuery;

        var $existing = $('#delivery-pending-bar');
        if (!items || !items.length) {
            $existing.hide();
            return;
        }

        // สร้าง text (ไม่ duplicate)
        var text = items.map(function (i) {
            return i.barcode + '  (ค้าง ' + i.remaining + ' ' + (i.unit_name || 'ชิ้น') + ')';
        }).join('     ·     ');

        if ($existing.length) {
            var $content = $existing.find('.pb-content');
            $content.text(text);
            // ตรวจสอบว่าต้อง scroll ไหม
            var trackWidth = $existing.find('.pb-track')[0].offsetWidth;
            var contentWidth = $content[0].scrollWidth;
            if (contentWidth > trackWidth) {
                $content.addClass('scrolling').css(
                    'animation-duration', Math.max(15, items.length * 5) + 's'
                );
            } else {
                $content.removeClass('scrolling').css('animation-duration', '');
            }
            $existing.show();
            return;
        }

        injectPendingBarStyles();

        var $bar = $([
            '<div id="delivery-pending-bar">',
            '  <span class="pb-label">📋 ค้างส่ง:</span>',
            '  <div class="pb-track">',
            '    <span class="pb-content"></span>',
            '  </div>',
            '</div>',
        ].join(''));

        $bar.find('.pb-content').text(text);

        // แทรก bar ก่อน "Add another" link (ขึ้นไปอยู่เหนือมัน)
        var $anchor = findAddAnotherAnchor($);
        if ($anchor && $anchor.length) {
            // หา parent ที่ใกล้สุด (อาจเป็น div, p, หรือ tr)
            var $parent = $anchor.parent();
            $parent.before($bar);
        } else {
            // fallback: ต่อท้าย body
            $('body').append($bar);
        }

        // ตรวจสอบว่าต้อง scroll ไหม (ต้องทำหลัง insert เพื่อให้ได้ width จริง)
        setTimeout(function () {
            var $content = $bar.find('.pb-content');
            var trackWidth = $bar.find('.pb-track')[0].offsetWidth;
            var contentWidth = $content[0].scrollWidth;
            if (contentWidth > trackWidth) {
                $content.addClass('scrolling').css(
                    'animation-duration', Math.max(15, items.length * 5) + 's'
                );
            }
        }, 50);
    }

    function loadPendingBar() {
        if (!soId) return;
        fetch('/api/pending-barcodes/?so_id=' + encodeURIComponent(soId))
            .then(function (r) { return r.json(); })
            .then(function (data) { renderPendingBar(data.items); })
            .catch(function () {});
    }

    document.addEventListener('DOMContentLoaded', function () {
        setTimeout(initAllRows, 300);
        setTimeout(loadPendingBar, 500);

        // MutationObserver: จับ row ที่เพิ่มมาแบบ dynamic ได้แน่นอน ไม่ต้องพึ่ง formset:added
        var observer = new MutationObserver(function (mutations) {
            mutations.forEach(function (mutation) {
                mutation.addedNodes.forEach(function (node) {
                    if (node.nodeType !== 1) return; // element nodes only
                    if (node.tagName === 'TR') {
                        // row ถูก insert โดยตรง
                        setTimeout(function () { setupRow(node); }, 50);
                    } else {
                        // node อื่น (เช่น tbody) ที่มี TR ข้างใน
                        node.querySelectorAll('tr').forEach(function (tr) {
                            setTimeout(function () { setupRow(tr); }, 50);
                        });
                    }
                });
            });
        });

        observer.observe(document.body, { childList: true, subtree: true });

        // formset:added เป็น safety net เพิ่มเติม
        if (window.django && django.jQuery) {
            django.jQuery(document).on('formset:added', function (e, $row) {
                setTimeout(function () { setupRow($row[0]); }, 150);
            });
        }
    });

}());
