(function () {
    'use strict';

    // ---- SalesItemInline (รายการที่จะขาย): เติมเลขลำดับหน้าแต่ละแถว ----
    // เปรมพิมพ์ 100 กว่ารายการแล้วจำไม่ได้ว่าถึงลำดับไหนแล้ว — ใส่คอลัมน์ "#" ไว้หน้าสุด
    // ทำงานล้วนๆ ฝั่ง client (ไม่แตะ model/DB) นับเฉพาะแถวที่ "เห็นอยู่จริง" และยังไม่ถูกติ๊กลบ
    // แถว template ว่างของ formset (empty-form) ถูกซ่อนด้วย display:none อยู่แล้ว จึงไม่ถูกนับ/ไม่โดนแทรกคอลัมน์

    var PREFIX = 'items'; // related_name ของ SalesItem → SalesOrder (ดู models.py)

    document.addEventListener('DOMContentLoaded', function () {
        var anchor = document.querySelector('[name^="' + PREFIX + '-0-"]');
        var table = anchor && anchor.closest('table');
        if (!table) return;

        function isVisible(tr) {
            return !!(tr.offsetWidth || tr.offsetHeight || tr.getClientRects().length);
        }

        function isMarkedDeleted(tr) {
            var del = tr.querySelector('input[name^="' + PREFIX + '-"][name$="-DELETE"]');
            return !!(del && del.checked);
        }

        function isHeaderRow(tr) {
            return !tr.querySelector('[name]') && !!tr.querySelector('th');
        }

        function ensureCell(tr, isHeader) {
            var cell = tr.querySelector(':scope > .so-item-row-number');
            if (cell) return cell;
            cell = document.createElement(isHeader ? 'th' : 'td');
            cell.className = 'so-item-row-number';
            cell.style.cssText = 'text-align:center;color:#6b7280;font-variant-numeric:tabular-nums;';
            tr.insertBefore(cell, tr.firstChild);
            return cell;
        }

        function setText(cell, text) {
            // เช็คก่อนค่อยเซ็ต กัน MutationObserver ยิงซ้ำเป็นลูปไม่จบจากการแก้ text ของตัวเอง
            if (cell.textContent !== String(text)) cell.textContent = text;
        }

        function renumber() {
            var n = 0;
            table.querySelectorAll('tr').forEach(function (tr) {
                if (isHeaderRow(tr)) {
                    setText(ensureCell(tr, true), '#');
                    return;
                }
                if (!isVisible(tr)) return;
                var cell = ensureCell(tr, false);
                if (isMarkedDeleted(tr)) {
                    setText(cell, '');
                    return;
                }
                n += 1;
                setText(cell, n);
            });
        }

        var scheduled = false;
        function scheduleRenumber() {
            if (scheduled) return;
            scheduled = true;
            setTimeout(function () {
                scheduled = false;
                renumber();
            }, 0);
        }

        renumber();

        document.addEventListener('formset:added', scheduleRenumber);
        document.addEventListener('formset:removed', scheduleRenumber);
        table.addEventListener('change', function (e) {
            if (e.target.name && e.target.name.indexOf(PREFIX + '-') === 0 && e.target.name.slice(-7) === '-DELETE') {
                scheduleRenumber();
            }
        });

        // สังเกตแค่ tbody ระดับ "ลูกตรง" (ไม่เอา subtree) — ดักเฉพาะแถวถูกเพิ่ม/ลบจริงๆ
        // (ตอนกด "Add another"/"Remove") ไม่ยุ่งกับการแก้ text ในเซลล์ที่เราเพิ่งแทรกเอง
        // ซึ่งอยู่ลึกกว่านั้น (tr > td) เพื่อกันไม่ให้ observer ยิงตัวเองเป็นลูป
        var tbody = table.tBodies && table.tBodies[0];
        if (window.MutationObserver && tbody) {
            new MutationObserver(scheduleRenumber).observe(tbody, { childList: true });
        }
    });
}());
