(function () {
    'use strict';

    // หน้าใบสั่งซื้อ: คำนวณ "จำนวนรวม (ชิ้น)" และ "Total price" ทันทีที่กรอก (ไม่ต้องกดบันทึก)
    //  จำนวนรวม = จำนวนที่สั่ง (ตามหน่วย) x จำนวนต่อหน่วยของบาร์โค้ด (ไม่เลือกบาร์โค้ด = x1) ตัดเศษเหมือนตอนบันทึก
    //  Total = จำนวนรวม x ราคา/หน่วย (สกุลของใบ) — สกุลอื่นที่มีเรทแล้ว ต่อท้ายยอดบาท (≈ ... บาท)
    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$ || !document.getElementById('id_supplier')) return;  // ไม่ใช่หน้าใบสั่งซื้อ

        var factors = {};  // barcode id -> จำนวนต่อหน่วย (ดึงจาก /api/barcode-info/ ครั้งเดียวต่อบาร์โค้ด)

        function money(n) {
            return n.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
        }

        function cell($row, field) {
            return $row.find('td.field-' + field + ' .readonly').first();
        }

        function render($row, factor) {
            var qtyUnit = parseFloat($row.find('input[name$="-quantity_unit"]').val());
            var price = parseFloat($row.find('input[name$="-unit_price"]').val());
            var $qty = cell($row, 'quantity_ordered'), $total = cell($row, 'total_price');
            if (!(qtyUnit >= 0)) { $qty.text('-'); $total.text('-'); return; }
            var pieces = Math.trunc(qtyUnit * factor);
            $qty.text(pieces.toLocaleString('en-US'));
            if (!(price >= 0)) { $total.text('-'); return; }
            var total = pieces * price;
            var currency = (document.getElementById('id_currency') || {}).value || 'THB';
            var rate = parseFloat((document.getElementById('id_exchange_rate') || {}).value);
            var text = money(total);
            if (currency !== 'THB' && rate > 0 && rate !== 1) text += ' (≈ ' + money(total * rate) + ' บาท)';
            $total.text(text);
        }

        function update(row) {
            var $row = $(row);
            if (!$row.find('input[name$="-quantity_unit"]').length) return;
            var barcodeId = $row.find('select[name$="-barcode_obj"]').val();
            if (!barcodeId) { render($row, 1); return; }
            if (factors[barcodeId] !== undefined) { render($row, factors[barcodeId]); return; }
            $.get('/api/barcode-info/', {barcode_id: barcodeId}).done(function (d) {
                factors[barcodeId] = parseFloat(d && d.conversion_factor) || 1;
                render($row, factors[barcodeId]);
            });
        }

        function updateAll() {
            $('input[name$="-quantity_unit"]').each(function () {
                if (!/__prefix__/.test(this.name)) update($(this).closest('tr'));
            });
        }

        $(document).on('input change', 'input[name$="-quantity_unit"], input[name$="-unit_price"]', function () {
            update($(this).closest('tr'));
        });
        $(document).on('change', 'select[name$="-barcode_obj"]', function () { update($(this).closest('tr')); });
        // เปลี่ยนสกุลเงิน/เรท -> ยอดบาทที่ต่อท้ายเปลี่ยนตาม
        $(document).on('input change', '#id_currency, #id_exchange_rate', updateAll);
        $(document).on('formset:added', function (e, $row) { if ($row) update($row); });
    });
}());
