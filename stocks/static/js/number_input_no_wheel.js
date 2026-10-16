(function () {
    'use strict';

    // ช่อง input type="number" (ราคา/จำนวน ฯลฯ) — ถ้าโฟกัสค้างอยู่แล้วเลื่อนลูกกลิ้งเมาส์
    // browser จะเพิ่ม/ลดค่าเอง ทำให้ตัวเลขเปลี่ยนโดยไม่ตั้งใจ
    // ให้ blur ช่องนั้นทิ้งก่อน ค่าจะไม่เปลี่ยน และหน้าเว็บยังเลื่อนขึ้นลงได้ตามปกติ
    // (แก้ค่าได้เฉพาะการพิมพ์ตัวเลขจากคีย์บอร์ดเท่านั้น)
    function isNumberInput(el) {
        return !!el && el.tagName === 'INPUT' && (el.type || '').toLowerCase() === 'number';
    }

    document.addEventListener('wheel', function (e) {
        var el = document.activeElement;
        if (!isNumberInput(el)) return;
        if (e.target === el || el.contains(e.target)) {
            el.blur();
        }
    }, { capture: true, passive: true });

    // ปิดการกดลูกศรขึ้น/ลงเพิ่ม/ลดค่าในช่องตัวเลขด้วย
    document.addEventListener('keydown', function (e) {
        if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
        if (!isNumberInput(e.target)) return;
        e.preventDefault();
    }, true);
}());
