(function () {
    'use strict';

    // ช่อง input type="number" (ราคา/จำนวน ฯลฯ) — ถ้าโฟกัสค้างอยู่แล้วเลื่อนลูกกลิ้งเมาส์
    // browser จะเพิ่ม/ลดค่าเอง ทำให้ตัวเลขเปลี่ยนโดยไม่ตั้งใจ
    // ให้ blur ช่องนั้นทิ้งก่อน ค่าจะไม่เปลี่ยน และหน้าเว็บยังเลื่อนขึ้นลงได้ตามปกติ
    // (แก้ค่าได้เฉพาะการพิมพ์จากคีย์บอร์ดเท่านั้น)
    document.addEventListener('wheel', function (e) {
        var el = document.activeElement;
        if (!el || el.tagName !== 'INPUT' || (el.type || '').toLowerCase() !== 'number') return;
        if (e.target === el || el.contains(e.target)) {
            el.blur();
        }
    }, { capture: true, passive: true });
}());
