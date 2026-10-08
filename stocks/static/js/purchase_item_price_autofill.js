(function () {
    'use strict';

    // หน้าใบสั่งซื้อ (PurchaseOrder add/change)
    //  - เลือกสินค้าตัวแรก (ยังไม่ได้เลือกสกุลเงินเอง) -> ตั้งสกุลเงิน + เรทของใบตามที่ตั้งไว้กับ supplier นี้
    //  - เติมราคาซื้อจาก supplier (สกุลของใบ) เฉพาะตอนช่องราคายังว่าง/0 — ต้องแปลงสกุลแต่ยังไม่มีเรท = ไม่เติม
    //  - กล่องเตือน: สกุลอื่นที่ไม่ใช่บาทแต่ยังไม่กรอกเรท / สินค้าในใบมีหลายสกุลเงิน / สกุลสินค้าไม่ตรงกับใบ
    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        var $supplierField = $('#id_supplier');
        if (!$supplierField.length) return; // ไม่ใช่หน้า PurchaseOrder add/change
        var currency = document.getElementById('id_currency');
        var rate = document.getElementById('id_exchange_rate');
        var LABELS = {THB: 'บาท', RMB: 'RMB', USD: 'USD'};

        function curValue() { return currency ? currency.value : 'THB'; }
        function rateMissing() {
            var r = parseFloat(rate && rate.value);
            return curValue() !== 'THB' && (!(r > 0) || r === 1);
        }

        function productSelects() {
            return $('select[name$="-product"]').filter(function () {
                if (!this.value || /__prefix__/.test(this.name)) return false;
                return !$(this).closest('tr').find('input[name$="-DELETE"]').prop('checked');
            });
        }

        // ---- กล่องเตือน (ใต้บรรทัด เลข Invoice / สกุลเงิน / ExRate) ----
        var $box = $('<div id="po-currency-warning" style="display:none;margin:8px 12px;padding:10px 12px;' +
            'border:1px solid #f59e0b;background:#fffbeb;color:#92400e;border-radius:6px;font-size:13px;line-height:1.5;"></div>');
        var $row = $('.form-row').has('.field-invoice_no_supplier').first();
        if ($row.length) $row.after($box); else $('#purchaseorder_form').prepend($box);

        var checkSeq = 0;
        function check() {
            var seq = ++checkSeq;
            var ids = productSelects().map(function () { return this.value; }).get();
            var render = function (serverWarnings) {
                if (seq !== checkSeq) return;
                var w = (serverWarnings || []).slice();
                if (rateMissing()) w.unshift('ยังไม่ได้กรอก ExRate ของสกุล ' + (LABELS[curValue()] || curValue()) + ' (บาทต่อ 1 หน่วยเงิน)');
                if (!w.length) { $box.hide().empty(); return; }
                $box.html(w.map(function (t) { return '⚠️ ' + $('<span>').text(t).html(); }).join('<br>')).show();
            };
            if (!$supplierField.val() || !ids.length) { render([]); return; }
            $.get('/api/po-product-currency/', {
                supplier_id: $supplierField.val(), product_ids: ids.join(','), currency: curValue(),
            }).done(function (d) { render(d && d.warnings); }).fail(function () { render([]); });
        }

        function fillPrice($row, productId, info) {
            var $priceInput = $row.find('input[name$="-unit_price"]');
            if (!$priceInput.length || parseFloat($priceInput.val())) return; // มีราคาอยู่แล้ว ไม่ทับ
            var sameCurrency = info && info.currency === curValue();
            if (!sameCurrency && rateMissing()) return; // ต้องแปลงสกุลแต่ยังไม่มีเรท -> ไม่เดาราคา
            $.get('/api/purchase-quotation-price/', {
                supplier_id: $supplierField.val(),
                product_id: productId,
                currency: curValue(),
                exchange_rate: (rate && rate.value) || '1',
            }).done(function (data) {
                if (!data || data.suggested_price === undefined) return;
                $priceInput.val(data.suggested_price);
            });
        }

        $(document).on('change', 'select[name$="-product"]', function () {
            var select = this;
            var productId = select.value;
            if (!productId) { check(); return; }
            var $row = $(select).closest('tr');
            var others = productSelects().filter(function () { return this !== select; }).length;
            $.get('/api/po-product-currency/', {supplier_id: $supplierField.val(), product_ids: productId})
                .done(function (d) {
                    var info = d && d.products ? d.products[productId] : null;
                    // สินค้าตัวแรกของใบ + ยังไม่ได้เลือกสกุลเงินเอง -> ใช้สกุล/เรทที่ตั้งไว้ของสินค้านี้
                    if (info && currency && !window.poCurrencyUserPicked && others === 0 && info.currency !== curValue()) {
                        currency.value = info.currency;
                        var r = parseFloat(info.exchange_rate);
                        rate.value = info.currency === 'THB' ? '1' : (r > 1 ? info.exchange_rate : '');
                        if (window.poCurrencySync) window.poCurrencySync();
                    }
                    fillPrice($row, productId, info);
                    check();
                });
        });

        $(document).on('change', '#id_currency, #id_exchange_rate, #id_supplier, input[name$="-DELETE"]', check);
        $(document).on('input', '#id_exchange_rate', check);
        $(document).on('formset:removed', check);
        check();
    });

}());
