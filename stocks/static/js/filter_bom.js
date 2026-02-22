// static/js/filter_bom.js
(function() {
    var initFilter = function($) {
        $(document).ready(function() {
            function updateBOMOptions() {
                var productSelect = $('#id_product');
                var bomSelect = $('#id_bom');
                
                // ดึงชื่อสินค้าที่เลือก (ตัดช่องว่างหน้าหลัง)
                var selectedProduct = productSelect.find('option:selected').text().trim();
                
                if (!selectedProduct || selectedProduct.indexOf('----') !== -1) {
                    bomSelect.find('option').show();
                    return;
                }

                bomSelect.find('option').each(function() {
                    var option = $(this);
                    if (!option.val()) return; // ข้ามตัวเลือกว่าง

                    // 🎯 กรอง: ถ้าชื่อ BOM มีชื่อสินค้าอยู่ข้างใน ให้แสดง
                    if (option.text().indexOf(selectedProduct) !== -1) {
                        option.show().prop('disabled', false);
                    } else {
                        option.hide().prop('disabled', true);
                        if (bomSelect.val() === option.val()) {
                            bomSelect.val(''); // ล้างค่าถ้าตัวที่เลือกถูกซ่อน
                        }
                    }
                });
            }

            // ดักฟังการเปลี่ยนค่า (รองรับทั้ง Select ปกติและ Select2)
            $(document).on('change', '#id_product', function() {
                updateBOMOptions();
            });

            // รันทันทีที่โหลดหน้าจอ
            updateBOMOptions();
        });
    };

    // 🎯 ตรวจสอบความพร้อมของ django.jQuery
    var checkInterval = setInterval(function() {
        if (typeof django !== 'undefined' && django.jQuery) {
            initFilter(django.jQuery);
            clearInterval(checkInterval);
        }
    }, 100);
})();