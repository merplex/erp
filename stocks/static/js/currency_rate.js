// สกุลเงิน + ExRate (ราคา Supplier ในหน้าสินค้า/ผู้จำหน่าย, หัวใบสั่งซื้อ)
//  - บาท -> เรท = 1 และล็อกช่อง (readonly ไม่ใช่ disabled เพื่อให้ค่ายังถูกส่งไปบันทึก)
//  - หน้าใบสั่งซื้อ: เปลี่ยนสกุลเงินเอง -> เติมเรทจากราคาที่ตั้งไว้ของ supplier นี้ (แก้เองได้)
//    หัวคอลัมน์ "ราคา/หน่วย" แสดงสกุลเงินของใบ / ตั้งสกุลเงินอัตโนมัติจากสินค้า: purchase_item_price_autofill.js
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        function rateFor(select) {
            var name = select.name.replace(/currency$/, 'exchange_rate');
            return document.querySelector('input[name="' + name + '"]');
        }

        function syncLock(select) {
            var rate = rateFor(select);
            if (!rate) return;
            var isThb = select.value === 'THB';
            if (isThb) rate.value = '1';
            rate.readOnly = isThb;
            rate.style.background = isThb ? '#f1f5f9' : '';
        }

        function lockAll() {
            document.querySelectorAll('select[name$="currency"]').forEach(syncLock);
        }
        lockAll();
        // ฟังแบบ native (capture) — ไม่พึ่ง jQuery: เลือกสกุลเงินด้วยวิธีไหนก็ล็อก/ปลดล็อกเรททันที
        document.addEventListener('change', function (e) {
            if (e.target && e.target.matches && e.target.matches('select[name$="currency"]')) syncLock(e.target);
        }, true);
        document.addEventListener('formset:added', lockAll);  // แถวใหม่ใน inline (Django 4.1+ ยิงเป็น native event)
        $(document).on('formset:added', lockAll);
        // กันพิมพ์/วางค่าในช่องเรทที่ล็อก (บางเบราว์เซอร์มือถือไม่เคารพ readonly ของ type=number)
        document.addEventListener('beforeinput', function (e) {
            var t = e.target;
            if (t && t.name && /exchange_rate$/.test(t.name) && t.readOnly) e.preventDefault();
        }, true);

        // ---- หน้าใบสั่งซื้อ ----
        var supplier = document.getElementById('id_supplier');
        var currency = document.getElementById('id_currency');
        var rate = document.getElementById('id_exchange_rate');
        if (!supplier || !currency || !rate) return;

        function labelPriceHeader() {
            var code = currency.value;
            document.querySelectorAll('th').forEach(function (th) {
                if (!th.dataset.baseLabel && /^ราคา\/หน่วย/.test(th.textContent.trim())) {
                    th.dataset.baseLabel = th.textContent.trim().replace(/\s*\(.*\)$/, '');
                }
                if (th.dataset.baseLabel) {
                    th.textContent = th.dataset.baseLabel + (code && code !== 'THB' ? ' (' + code + ')' : '');
                }
            });
        }
        labelPriceHeader();

        function fetchRate() {
            if (!supplier.value || currency.value === 'THB') return;
            $.get('/api/supplier-currency-rate/', {supplier_id: supplier.value, currency: currency.value})
                .done(function (data) {
                    if (data && data.exchange_rate) rate.value = data.exchange_rate;
                    $(rate).trigger('change');
                });
        }

        // ผู้ใช้เปลี่ยนสกุลเงินเอง -> เติมเรทจากราคา Supplier ของสกุลนั้น (แก้ได้)
        currency.addEventListener('change', function (e) {
            labelPriceHeader();
            if (e.isTrusted) { window.poCurrencyUserPicked = true; fetchRate(); }
        });
        // ให้ purchase_item_price_autofill.js เรียกหลังตั้งสกุลเงินอัตโนมัติจากสินค้า
        window.poCurrencySync = function () { syncLock(currency); labelPriceHeader(); };
    });
}());
