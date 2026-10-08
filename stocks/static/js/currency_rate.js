// สกุลเงิน + ExRate (ราคา Supplier ในหน้าสินค้า/ผู้จำหน่าย, หัวใบสั่งซื้อ)
//  - บาท -> เรท = 1 และล็อกช่อง (readonly ไม่ใช่ disabled เพื่อให้ค่ายังถูกส่งไปบันทึก)
//  - หน้าใบสั่งซื้อ: เลือก supplier/สกุลเงิน -> เติมเรทอัตโนมัติจากราคาที่ตั้งไว้ของ supplier นี้ (แก้เองได้)
//    และหัวคอลัมน์ "ราคา/หน่วย" ของรายการสินค้าแสดงสกุลเงินของใบ
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
        $(document).on('change', 'select[name$="currency"]', function () { syncLock(this); });
        $(document).on('formset:added', lockAll);  // แถวใหม่ใน inline

        // ---- หน้าใบสั่งซื้อ ----
        var supplier = document.getElementById('id_supplier');
        var currency = document.getElementById('id_currency');
        var rate = document.getElementById('id_exchange_rate');
        if (!supplier || !currency || !rate) return;
        var isNew = /\/add\/?$/.test(window.location.pathname);

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

        function fetchRate(pickCurrency) {
            if (!supplier.value) return;
            $.get('/api/supplier-currency-rate/', {
                supplier_id: supplier.value,
                currency: pickCurrency ? '' : currency.value,
            }).done(function (data) {
                if (!data) return;
                if (pickCurrency && data.currency && data.currency !== currency.value) {
                    currency.value = data.currency;
                    syncLock(currency);
                    labelPriceHeader();
                }
                if (data.exchange_rate && currency.value !== 'THB') rate.value = data.exchange_rate;
            });
        }

        $(currency).on('change', function () { labelPriceHeader(); fetchRate(false); });
        // ใบใหม่: เลือก supplier -> เลือกสกุลเงิน/เรทที่ใช้กับ supplier นี้ล่าสุดให้ (เปลี่ยนเองได้)
        $(supplier).on('change', function () { if (isNew) fetchRate(true); });
    });
}());
