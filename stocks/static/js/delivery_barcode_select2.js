(function () {
    'use strict';

    var soId = (window.location.pathname.match(/\/(\d+)\/change\//) || [])[1];

    function checkBarcode($input) {
        var code = ($input.val() || '').trim();
        var $td = $input.closest('td');
        var $hint = $td.find('.barcode-hint');

        if (!$hint.length) {
            $hint = $('<div class="barcode-hint" style="font-size:12px;margin-top:3px;font-weight:bold;"></div>');
            $input.after($hint);
        }

        if (!code) {
            $input.css('border-color', '');
            $hint.text('').hide();
            return;
        }

        if (!soId) {
            $hint.text('').hide();
            return;
        }

        // AJAX ไป API ของเราเอง
        fetch('/api/barcode-remaining/?so_id=' + encodeURIComponent(soId) + '&barcode=' + encodeURIComponent(code))
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.valid) {
                    $input.css('border-color', '#22c55e');
                    var rem = data.remaining;
                    if (rem > 0) {
                        $hint.text('คงเหลือ: ' + rem + ' ชิ้น').css('color', '#16a34a').show();
                    } else {
                        $hint.text('ส่งครบแล้ว (0)').css('color', '#dc2626').show();
                    }
                } else {
                    $input.css('border-color', '#dc2626');
                    $hint.text(data.error || 'ไม่พบบาร์โค้ด').css('color', '#dc2626').show();
                }
            })
            .catch(function () {
                $hint.text('').hide();
            });
    }

    function setupRow(row) {
        var input = row.querySelector('input.barcode-code-input:not([readonly])');
        if (!input) return;
        var $input = window.django ? django.jQuery(input) : null;
        if (!$input) return;

        var timer = null;

        $input.on('input', function () {
            clearTimeout(timer);
            timer = setTimeout(function () { checkBarcode($input); }, 500);
        });

        $input.on('blur', function () {
            clearTimeout(timer);
            checkBarcode($input);
        });
    }

    function init() {
        document.querySelectorAll('input.barcode-code-input:not([readonly])').forEach(function (el) {
            setupRow(el.closest('tr') || el.parentElement);
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        setTimeout(init, 300);

        // รองรับแถวที่เพิ่มใหม่ด้วย "Add another"
        if (window.django && django.jQuery) {
            django.jQuery(document).on('formset:added', function (e, $row) {
                setTimeout(function () { setupRow($row[0]); }, 100);
            });
        }
    });

}());
