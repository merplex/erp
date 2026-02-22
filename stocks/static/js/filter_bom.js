// static/js/filter_bom.js
(function($) {
    $(document).ready(function() {
        // ดักฟังเหตุการณ์เมื่อช่อง Product (id_product) เปลี่ยนแปลง
        $('#id_product').on('change', function() {
            var productId = $(this).val();
            var bomSelect = $('#id_bom');
            
            // ล้างค่าในช่อง BOM ก่อน
            bomSelect.val(null).trigger('change');
            
            // ถ้าไม่มีการเลือกสินค้า ให้โชว์ทั้งหมด หรือซ่อนไว้
            if (!productId) {
                bomSelect.find('option').show();
                return;
            }

            // กรอง Option ในช่อง BOM
            bomSelect.find('option').each(function() {
                var optionText = $(this).text();
                // ดึงชื่อสินค้าออกมาจากชื่อ BOM (ที่เปรมทำไว้ใน __str__)
                // เช่น "สินค้า C - BOM C" -> จะเช็คว่ามีคำว่า "สินค้า C" ไหม
                var productName = $('#id_product').find('option:selected').text();
                
                if (optionText.includes(productName) || $(this).val() === "") {
                    $(this).show();
                } else {
                    $(this).hide();
                }
            });
        });
    });
})(django.jQuery);