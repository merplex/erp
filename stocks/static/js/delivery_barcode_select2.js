(function () {
    'use strict';

    var soId = (window.location.pathname.match(/\/(\d+)\/change\//) || [])[1];

    // จำนวน auto-save (AJAX) ที่กำลังยิงค้างอยู่ — ใช้กันไม่ให้กดปุ่ม Save หลักของหน้า
    // (ที่ submit ทั้งฟอร์มแบบปกติ) หลุดออกไปก่อนที่ auto-save จะอัปเดต hidden id field เสร็จ
    // ไม่งั้นแถวเดียวกันจะถูกสร้างซ้ำ 2 รายการ (อันจาก auto-save มีชื่อผู้บันทึก, อันจาก
    // Save ปกติไม่มี เพราะ user เป็น readonly field ไม่ได้ถูกตั้งค่าตรงนั้น)
    var pendingAutoSaves = 0;

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

    // ล้าง error message ของ Django (errorlist สีแดงจากการกด Save หน้าเต็ม) ในแถวนี้
    function clearRowServerErrors($row) {
        $row.find('.errorlist').remove();
        $row.find('.errors').removeClass('errors');
        $row.find('input, select, textarea').css('border-color', '');
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
                    // ✅ เลือกบาร์โค้ดที่มีอยู่จริงในใบสั่งขายนี้แล้วเท่านั้น ถึงค่อย auto-fill
                    // เลขใบขนส่ง/วันที่ส่งของจากแถวก่อนหน้าให้ — ถ้ายังไม่เลือกอะไรเลยจะไม่ auto-fill
                    var row = $input.closest('tr')[0];
                    if (row) {
                        autoFillShippingNo(row);
                        autoFillShippedDate(row);
                    }
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

        // 🎯 BUG หลักที่ทำให้บันทึกซ้ำไม่รู้จบ: แถวที่เพิ่มแบบ dynamic (กด "Add another") ไม่มีช่อง
        // hidden "-id" อยู่ใน DOM เลยสักที่เดียว — Unfold clone แค่ tbody ของช่องที่มองเห็น
        // (บาร์โค้ด/จำนวน/ฯลฯ) จาก .empty-form template แต่ไม่ได้ clone tbody ของ hidden field
        // (id/DELETE) มาด้วย (ยืนยันจาก debug จริง: idInputCount=0 เสมอสำหรับแถวที่เพิ่มใหม่)
        // ผลคือ logId เป็น null ตลอดไม่ว่า auto-save จะสำเร็จไปแล้วกี่รอบ เพราะไม่มีที่เก็บค่า
        // เลยส่ง POST แบบ "สร้างใหม่" ซ้ำทุกครั้งที่มีอะไรมา trigger (คลิกช่องอื่น, สลับหน้าต่างไป
        // แอปอื่นแล้วกลับมาก็ทำให้ field ที่ focus อยู่ blur เหมือนกัน) — แก้โดยดึง index ของแถวจาก
        // name ของช่องบาร์โค้ด (เช่น "delivery_logs-5-barcode_code" → index 5) แล้ว query หา id
        // field ทั้งหน้า ถ้าไม่เจอเลย (แถวใหม่) ให้สร้างขึ้นเองแปะไว้ในแถว จะได้มีที่เก็บ log_id
        // ไว้ใช้ครั้งต่อไป (ตอน submit ฟอร์มจริงก็จะถูกส่งไปด้วย เพราะอยู่ใน <form> เหมือนกัน)
        var nameMatch = ($barcodeInput.attr('name') || '').match(/-(\d+)-barcode_code$/);
        var $idInput = nameMatch
            ? django.jQuery('input[name="delivery_logs-' + nameMatch[1] + '-id"]')
            : $row.find('input[name$="-id"]'); // fallback เผื่อโครงสร้างเปลี่ยนไปจากนี้
        if (nameMatch && $idInput.length === 0) {
            $idInput = django.jQuery('<input type="hidden">')
                .attr('name', 'delivery_logs-' + nameMatch[1] + '-id')
                .attr('id', 'id_delivery_logs-' + nameMatch[1] + '-id');
            $row.append($idInput);
        }
        var logId = $idInput.val() || null;

        var shippingNo  = ($row.find('input[name*="delivery_logs-"][name$="-shipping_no"]').val() || '').trim();
        var notes       = ($row.find('input[name*="delivery_logs-"][name$="-notes"]').val() || '').trim();
        var shippedDate = ($row.find('input[name*="delivery_logs-"][name$="-shipped_date"]').val() || '').trim();

        $row.data('saving', true);
        pendingAutoSaves++;
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
            pendingAutoSaves--;
            if (result.success) {
                // อัปเดต id hidden field → กด Save ใหญ่จะ UPDATE ไม่ใช่ CREATE ซ้ำ
                if (!$idInput.val()) {
                    $idInput.val(result.log_id);
                }
                // ล้าง error เก่า (เช่น "ไม่พบบาร์โค้ดนี้ในระบบ" / "This field is required."
                // ที่ค้างมาจากการกด Save หน้าเต็มครั้งก่อน) ไม่งั้นจะค้างคาอยู่ทั้งที่ auto-save
                // รอบนี้สำเร็จแล้ว ทำให้ดูเหมือนขัดแย้งกันเอง (บันทึกแล้ว แต่ก็ยัง error)
                clearRowServerErrors($row);
                // ล็อค barcode
                lockBarcodeInput($barcodeInput);
                // อัปเดต remaining
                var rem = result.remaining;
                var unit = result.unit_name || 'ชิ้น';
                showHint($barcodeInput,
                    '✓ บันทึกแล้ว' + (rem > 0 ? ' — คงเหลือ: ' + rem + ' ' + unit : ' — ส่งครบแล้ว'),
                    rem > 0 ? '#16a34a' : '#2563eb'
                );
                // รีเฟรชแถบ "ค้างส่ง" ให้ตรงกับยอดล่าสุด (ไม่งั้นจะค้างข้อมูลเก่าตั้งแต่โหลดหน้า)
                loadPendingBar();
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
            pendingAutoSaves--;
            console.error('Autosave error:', err);
        });
    }

    // หา delivery row ที่อยู่เหนือ row นี้ขึ้นไป
    // รองรับทั้ง: rows ใน tbody เดียวกัน และ Unfold ที่แยก tbody ต่อ row
    function getPrevDeliveryRow(row) {
        // ลองหาใน sibling ของ row เดียวกันก่อน
        var prev = row.previousElementSibling;
        while (prev) {
            if (prev.querySelector('input[name*="delivery_logs-"][name$="-shipping_no"]')) {
                return prev;
            }
            prev = prev.previousElementSibling;
        }
        // fallback: Unfold แยก tbody ต่อ row — ดู parent siblings
        var parent = row.parentElement;
        if (!parent) return null;
        var prevParent = parent.previousElementSibling;
        while (prevParent) {
            var found = prevParent.querySelector('input[name*="delivery_logs-"][name$="-shipping_no"]');
            if (found) return found.closest('tr');
            prevParent = prevParent.previousElementSibling;
        }
        return null;
    }

    // copy shipping_no จาก row ก่อนหน้า ถ้า row ปัจจุบันยังว่าง
    function autoFillShippingNo(row) {
        if (!window.django) return;
        var $ = django.jQuery;
        var $snInput = $(row).find('input[name*="delivery_logs-"][name$="-shipping_no"]');
        if (!$snInput.length || $snInput.val().trim()) return; // มีค่าแล้ว ไม่ copy
        var prevRow = getPrevDeliveryRow(row);
        if (!prevRow) return;
        var prevVal = $(prevRow).find('input[name*="delivery_logs-"][name$="-shipping_no"]').val().trim();
        if (prevVal) $snInput.val(prevVal);
    }

    // แถวที่มีอยู่แล้วตั้งแต่เปิดหน้า (มี -id ไม่ว่าง = บันทึกไว้จากรอบก่อนหน้าแล้ว)
    // ใช้กันไม่ให้ copy วันที่ส่งของเก่าข้ามรอบมาโดยไม่ตั้งใจ
    function markPreexistingRows() {
        if (!window.django) return;
        var $ = django.jQuery;
        $('input[name*="delivery_logs-"][name$="-id"]').each(function () {
            if (($(this).val() || '').trim()) {
                $(this).closest('tr').data('deliveryPreexisting', true);
            }
        });
    }

    // copy วันที่ส่งของจาก row ก่อนหน้า ถ้า row ปัจจุบันยังว่าง
    // — แต่ copy ได้เฉพาะจาก row ที่ "เพิ่มใหม่ในรอบนี้" เท่านั้น (ไม่ copy จาก row เก่าที่บันทึก
    // ไว้ตั้งแต่รอบก่อนหน้า) กันพลาดกรอกวันที่ผิดตอนเปิดเอกสารเก่ามาเพิ่มรายการส่งของใหม่
    function autoFillShippedDate(row) {
        if (!window.django) return;
        var $ = django.jQuery;
        var $dateInput = $(row).find('input[name*="delivery_logs-"][name$="-shipped_date"]');
        if (!$dateInput.length || $dateInput.val().trim()) return; // มีค่าแล้ว ไม่ copy
        var prevRow = getPrevDeliveryRow(row);
        if (!prevRow) return;
        if ($(prevRow).data('deliveryPreexisting')) return; // row ก่อนหน้าเป็นของเก่า ต้องกรอกเองก่อน
        var prevVal = $(prevRow).find('input[name*="delivery_logs-"][name$="-shipped_date"]').val().trim();
        if (prevVal) $dateInput.val(prevVal);
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

        // ผูก datalist ของบาร์โค้ดในใบสั่งขายนี้ → พิมพ์แค่บางส่วน (เช่น 4 หลัก) ก็กรองแล้วเลือกได้เลย
        // ไม่ต้องพิมพ์บาร์โค้ดเต็มๆ ทุกครั้ง
        $barcodeInput.attr('list', 'delivery-barcode-datalist');

        // ⚠️ ไม่ auto-fill shipping_no/shipped_date จนกว่าจะ "เลือกบาร์โค้ดที่ถูกต้องแล้ว" จริงๆ
        // (ดูใน checkBarcode ด้านบน — auto-fill จะทำงานตรงนั้นตอน data.valid เท่านั้น) ไม่ใช่แค่
        // คลิกโฟกัสช่องเฉยๆ หรือกำลังพิมพ์อยู่ ไม่งั้นแถวว่างท้ายตารางที่ผู้ใช้ยังไม่ได้เลือกอะไรเลย
        // จะถูกยัดค่าเข้าไป ทำให้ Django มองว่า row นี้ "มีข้อมูล" แล้วบังคับ validate ช่องอื่น
        // (บาร์โค้ด/จำนวน) ที่ยังว่างอยู่ กด Save ทั้งหน้าไม่ผ่านทั้งที่ตั้งใจปล่อยแถวนี้ว่างไว้
        var barcodeTimer = null;

        // ออกจากกล่อง barcode → validate + ลอง save (ถ้ามี qty แล้ว)
        $barcodeInput.on('blur', function () {
            clearTimeout(barcodeTimer);
            checkBarcode($barcodeInput, function (valid) {
                if (valid) autoSaveRow($row);
            });
        });

        // พิมพ์ใน barcode → validate หลัง 600ms (auto-fill จะตามมาเองถ้า valid ดูใน checkBarcode)
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

        // ⚠️ ห้ามสร้าง/ล้าง <datalist id="delivery-barcode-datalist"> จาก items ของ endpoint นี้
        // — endpoint นี้กรองเฉพาะรายการที่ "ยังส่งไม่ครบ" (remaining > 0) เท่านั้น ถ้า SO ไหน
        // ส่งครบหมดแล้ว items จะว่างเปล่า แล้วมาล้าง datalist ที่ SalesOrderAdmin ฝังมาให้ตั้งแต่
        // render หน้า (ซึ่งมีบาร์โค้ดครบทุกรายการใน SO ไม่ใช่แค่ที่ยังค้างส่ง) จนกลายเป็นว่าง เคยเจอ
        // บั๊กนี้มาแล้ว — ปล่อยให้ datalist ที่ฝังมากับหน้าเป็นตัวหลักไปเลย ไม่ต้องมาสร้างซ้ำที่นี่

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
        // ต้องทำก่อน initAllRows เสมอ เพื่อจับสถานะ "แถวเก่าที่บันทึกไว้แล้วตั้งแต่ก่อนเปิดหน้านี้"
        // ไว้ก่อนที่ auto-fill วันที่จะเริ่มทำงาน
        markPreexistingRows();
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

    // ⚠️ กันกด Save/Save and continue editing หลุดออกไปก่อน auto-save (blur) ที่พึ่งยิงจะเสร็จ
    // ไม่งั้นแถวเดียวกันจะถูกสร้างซ้ำ 2 รายการในฐานข้อมูล (ดูคอมเมนต์ตรง pendingAutoSaves ด้านบน)
    // ต้องดักที่ document ช่วง capture phase เพื่อให้ทำงานก่อน listener อื่นๆ ของหน้า (เช่น
    // ตัวกันกด submit ซ้ำใน smart_delivery_inline.js)
    document.addEventListener('submit', function (e) {
        if (pendingAutoSaves <= 0) return;
        var form = e.target;
        if (!(form instanceof HTMLFormElement)) return;
        e.preventDefault();
        e.stopImmediatePropagation();
        var submitter = e.submitter; // ปุ่มที่ถูกกด (Save / Save and continue editing / ...)

        // แสดงให้เห็นชัดว่ากำลังรอ auto-save ที่ค้างอยู่ ไม่ใช่ปุ่มค้าง/หน้าพัง —
        // จะขึ้นแค่แป๊บเดียวเท่าที่ auto-save ใช้จริง (เช็คทุก 100ms พอเสร็จก็ submit ทันที
        // ไม่ต้องรอครบเวลา) 2500ms คือเพดานกันไว้เฉยๆ เผื่อ network ค้างจริงๆ เท่านั้น
        var originalValue = submitter ? submitter.value : null;
        if (submitter) {
            submitter.disabled = true;
            submitter.value = '⏳ กำลังบันทึก...';
        }

        var waited = 0;
        var maxWaitMs = 2500;
        var check = setInterval(function () {
            waited += 100;
            if (pendingAutoSaves > 0 && waited < maxWaitMs) return;
            clearInterval(check);
            // ใส่ name/value ของปุ่มที่กดไว้กลับเข้าไป (ค่าดั้งเดิม ไม่ใช่ "กำลังบันทึก...")
            // เพราะ requestSubmit() แบบไม่ระบุปุ่มจะไม่ส่งค่านี้ ทำให้ Django ไม่รู้ว่าจะ
            // redirect ไปหน้าไหนหลังบันทึก
            if (submitter && submitter.name) {
                var hidden = document.createElement('input');
                hidden.type = 'hidden';
                hidden.name = submitter.name;
                hidden.value = originalValue;
                form.appendChild(hidden);
            }
            if (form.requestSubmit) {
                form.requestSubmit();
            } else {
                form.submit();
            }
        }, 100);
    }, true);

}());
