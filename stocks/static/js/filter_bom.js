// static/js/filter_bom.js
document.addEventListener('DOMContentLoaded', function() {
    const productSelect = document.querySelector('#id_product');
    const bomSelect = document.querySelector('#id_bom');

    if (productSelect && bomSelect) {
        productSelect.addEventListener('change', function() {
            const productName = productSelect.options[productSelect.selectedIndex].text;
            
            // วนลูปเช็คทุกตัวเลือกในช่องสูตรผลิต
            Array.from(bomSelect.options).forEach(option => {
                if (option.value === "") return; // ข้ามตัวเลือกว่าง
                
                // 🎯 ถ้าชื่อสินค้าในตัวเลือกสูตร ตรงกับชื่อสินค้าที่เลือก ให้แสดงผล
                if (option.text.startsWith(productName)) {
                    option.style.display = 'block';
                } else {
                    option.style.display = 'none';
                    if (bomSelect.value === option.value) bomSelect.value = ""; // ล้างค่าถ้าตัวที่เลือกอยู่ถูกซ่อน
                }
            });
        });
    }
});