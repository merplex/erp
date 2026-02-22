// static/js/filter_bom.js
(function($) {
    'use strict';
    $(function() {
        const productField = $('#id_product');
        const bomField = $('#id_bom');

        function updateBOMs() {
            // ดึงชื่อสินค้าที่เลือกอยู่ (ดึงจากตัวหนังสือใน Dropdown)
            const selectedProductText = productField.find('option:selected').text().trim();
            
            if (!selectedProductText || selectedProductText === '---------') {
                bomField.find('option').show();
                return;
            }

            bomField.find('option').each(function() {
                const option = $(this);
                if (!option.val()) return; // ข้ามช่องว่าง

                // 🎯 เช็คว่า "ชื่อสินค้า" ที่เราเลือก มีอยู่ใน "ชื่อสูตร BOM" หรือเปล่า
                // (เพราะเปรมทำ __str__ ไว้เป็น: "ชื่อสินค้า - ชื่อสูตร")
                if (option.text().includes(selectedProductText)) {
                    option.show().prop('disabled', false);
                } else {
                    option.hide().prop('disabled', true);
                    // ถ้าสูตรที่เคยเลือกไว้ถูกซ่อน ให้ล้างค่านั้นทิ้ง
                    if (bomField.val() === option.val()) {
                        bomField.val('');
                    }
                }
            });
        }

        // ดักฟังตอนเปลี่ยนสินค้า (ใช้ $(document) เพื่อรองรับ Select2 ของ Django)
        $(document).on('change', '#id_product', function() {
            updateBOMs();
        });

        // รันครั้งแรกตอนโหลดหน้า (เผื่อกดแก้ไขใบเดิม)
        updateBOMs();
    });
})(django.jQuery); // 🎯 ส่ง jQuery ของ Django เข้าไปใช้ในชื่อ $