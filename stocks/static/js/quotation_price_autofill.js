(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        var $supplierField = $('#id_supplier');
        var $customerField = $('#id_customer');
        var isPurchase = $supplierField.length > 0;
        var isSales = $customerField.length > 0;
        if (!isPurchase && !isSales) return;

        function fetchAndFillPrice($row, productId) {
            if (!productId) return;
            var $priceInput = $row.find('input[name$="-new_price"]');
            if (!$priceInput.length) return;

            var params = { product_id: productId };
            var url;
            if (isPurchase) {
                params.supplier_id = $supplierField.val();
                url = '/api/purchase-quotation-price/';
            } else {
                params.customer_id = $customerField.val();
                url = '/api/sales-quotation-price/';
            }

            $priceInput.css('opacity', 0.5);
            $.get(url, params)
                .done(function (data) {
                    if (data && data.price !== undefined) {
                        $priceInput.val(data.price);
                    }
                })
                .always(function () {
                    $priceInput.css('opacity', '');
                });
        }

        // ---- เลือกสินค้าในแต่ละแถว → ดึงราคาล่าสุดมาเติมให้ทันที ----
        $(document).on('change', 'select[name$="-product"]', function () {
            var $row = $(this).closest('tr');
            fetchAndFillPrice($row, this.value);
        });

        // ---- ใบเสนอราคาขาย: เลือกบาร์โค้ด → set product ให้ตรงกัน แล้วดึงราคาต่อ ----
        $(document).on('change', 'select[name$="-barcode"]', function () {
            var val = this.value;
            if (!val) return;
            var $row = $(this).closest('tr');
            var $productSelect = $row.find('select[name$="-product"]');
            if (!$productSelect.length) return;

            $.get('/api/barcode-info/', { barcode_id: val })
                .done(function (data) {
                    if (!data || !data.product_id) return;
                    if (String($productSelect.val()) !== String(data.product_id)) {
                        var newOption = new Option(data.product_name, data.product_id, true, true);
                        $productSelect.append(newOption).trigger('change');
                    } else {
                        fetchAndFillPrice($row, data.product_id);
                    }
                });
        });
    });

}());
