// ไฟล์นี้จะช่วยเปรมกรองบาร์โค้ดตามสินค้าที่เลือกในแถวนั้นๆ ค่ะ
(function($) {
    $(document).on('change', 'select[name$="-product"]', function() {
        var $row = $(this).closest('tr');
        var productId = $(this).val();
        var $barcodeField = $row.find('select[name$="-barcode"]');

        if (productId) {
            // เคลียร์ค่าเดิมในช่องบาร์โค้ดก่อน
            $barcodeField.val(null).trigger('change');
            
            // หมายเหตุ: ตรงนี้ถ้าเปรมอยากให้มันดึงบาร์โค้ดตัวแรกมาใส่ให้เลย 
            // เราต้องเขียน API เพิ่มเติมอีกนิดค่ะ แต่ขั้นต้นการมี Autocomplete 
            // ที่เปรมพิมพ์ชื่อสินค้าในช่องบาร์โค้ดได้เลย (จาก search_fields) จะช่วยได้มากค่ะ
        }
    });
})(django.jQuery);