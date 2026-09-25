// A8 ใบลดหนี้: เลือกใบกำกับภาษี/ใบส่งของ -> โหลดสินค้าในใบนั้นเข้า <datalist> ทันที (หน้าเพิ่ม)
// เลือกสินค้า (พิมพ์ชื่อ/บาร์โค้ด) แล้วโชว์ ราคาขาย / จำนวนในใบ / ยอดในใบ และคำนวณ มูลค่า / VAT / รวม VAT
// ตามจำนวนที่ลดหนี้ — ข้อมูลอยู่ใน window.CN_DATA (CreditNoteAdmin.render_change_form / receipt-items/)
(function () {
    var CELLS = ['get_unit_price', 'get_invoice_qty', 'get_invoice_total', 'get_amount', 'get_vat', 'get_total'];

    function fmt(n) {
        return Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function setCell(row, name, text) {
        var el = row.querySelector('td.field-' + name + ' .readonly');
        if (el) el.textContent = text;
    }

    function refresh(row, fillQty) {
        var data = window.CN_DATA;
        if (!data || !row) return;
        var search = row.querySelector('input.cn-item-search');
        var qtyInput = row.querySelector('input.cn-qty');
        var item = search ? data.items[search.value] : null;
        if (!item) {
            CELLS.forEach(function (n) { setCell(row, n, '-'); });
            return;
        }
        // เลือกสินค้าครั้งแรก -> ตั้งจำนวนเท่าจำนวนในใบ (ลดหนี้ได้ไม่เกินนี้) ให้แก้ต่อได้
        if (fillQty && qtyInput && !qtyInput.value) {
            qtyInput.value = item.qty;
        }
        var qty = qtyInput ? (parseFloat(qtyInput.value) || 0) : 0;
        var amount = item.price * qty;
        var vat = amount * data.vat / 100;
        setCell(row, 'get_unit_price', fmt(item.price));
        setCell(row, 'get_invoice_qty', Number(item.qty).toLocaleString('en-US'));
        setCell(row, 'get_invoice_total', fmt(item.price * item.qty));
        setCell(row, 'get_amount', fmt(amount));
        setCell(row, 'get_vat', fmt(vat));
        setCell(row, 'get_total', fmt(amount + vat));
    }

    function refreshAll() {
        document.querySelectorAll('input.cn-item-search').forEach(function (el) {
            refresh(el.closest('tr'), false);
        });
    }

    function loadReceipt(receiptId) {
        var data = window.CN_DATA;
        if (!data || !receiptId) return;
        fetch(data.items_url.replace('/0/', '/' + receiptId + '/'), { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (payload) {
                data.vat = payload.vat;
                data.items = payload.items;
                var list = document.getElementById('cn-item-options');
                if (list) {
                    list.innerHTML = '';
                    Object.keys(payload.items).forEach(function (label) {
                        var opt = document.createElement('option');
                        opt.value = label;
                        list.appendChild(opt);
                    });
                }
                refreshAll();
            });
    }

    function onEdit(e) {
        var t = e.target;
        if (!t.classList) return;
        if (t.classList.contains('cn-item-search')) refresh(t.closest('tr'), true);
        else if (t.classList.contains('cn-qty')) refresh(t.closest('tr'), false);
    }

    document.addEventListener('input', onEdit);
    document.addEventListener('change', onEdit);
    document.addEventListener('DOMContentLoaded', function () {
        var select = document.getElementById('id_receipt');
        if (select) {
            // ช่องใบกำกับเป็น autocomplete (select2) — event change ยิงผ่าน jQuery
            var $ = window.django && window.django.jQuery;
            if ($) $(select).on('change', function () { loadReceipt(select.value); });
            else select.addEventListener('change', function () { loadReceipt(select.value); });
            if (select.value) loadReceipt(select.value);  // กลับมาหน้าเดิมหลัง validate ไม่ผ่าน
        }
        refreshAll();
    });
})();
