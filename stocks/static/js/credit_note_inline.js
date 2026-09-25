// A8 ใบลดหนี้: เลือกสินค้า (พิมพ์ชื่อ/บาร์โค้ด จาก <datalist>) แล้วโชว์ ราคาขาย / จำนวนสั่ง / ยอดสั่ง ทันที
// และคำนวณ มูลค่า / VAT / มูลค่ารวม VAT ตามจำนวนที่ลดหนี้ — ข้อมูลมาจาก window.CN_DATA (CreditNoteAdmin.render_change_form)
(function () {
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
            ['get_unit_price', 'get_ordered_qty', 'get_ordered_total', 'get_amount', 'get_vat', 'get_total']
                .forEach(function (n) { setCell(row, n, '-'); });
            return;
        }
        // เลือกสินค้าครั้งแรก -> ตั้งจำนวนเท่ายอดที่ส่งแล้ว (ลดหนี้ได้ไม่เกินนี้) ให้แก้ต่อได้
        if (fillQty && qtyInput && !qtyInput.value) {
            qtyInput.value = Math.floor(item.shipped || item.ordered);
        }
        var qty = qtyInput ? (parseFloat(qtyInput.value) || 0) : 0;
        var amount = item.price * qty;
        var vat = amount * data.vat / 100;
        setCell(row, 'get_unit_price', fmt(item.price));
        setCell(row, 'get_ordered_qty', Number(item.ordered).toLocaleString('en-US'));
        setCell(row, 'get_ordered_total', fmt(item.price * item.ordered));
        setCell(row, 'get_amount', fmt(amount));
        setCell(row, 'get_vat', fmt(vat));
        setCell(row, 'get_total', fmt(amount + vat));
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
        document.querySelectorAll('input.cn-item-search').forEach(function (el) {
            if (el.value) refresh(el.closest('tr'), false);
        });
    });
})();
